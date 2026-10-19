// One-off: make Uptime Kuma notice an outage faster, by changing every monitor's check timing in
// its database. Run it inside the Kuma image so it uses Kuma's own sqlite module (see the commands
// in the comment at the bottom). Safe to run twice.
//
//   node tune.js --dry-run   print what would change, change nothing (Kuma can be running)
//   node tune.js             apply it (stop Kuma first, and take a backup)
//
// Fast monitors:  check every 20 s, retry after 20 s, 1 retry, 8 s timeout   -> down within ~45 s
// Slow monitors (names matching NAS|UniFi|UDM): 30 / 30 / 1 / 10             -> fewer false alarms
const sqlite3 = require("@louislam/sqlite3");

const dbPath = process.env.KUMA_DB || "/app/data/kuma.db";
const dryRun = process.argv.includes("--dry-run");
const FAST = { interval: 20, retry_interval: 20, maxretries: 1, timeout: 8 };
const SLOW = { interval: 30, retry_interval: 30, maxretries: 1, timeout: 10 };
const SKIP_TYPES = new Set(["group", "push", "manual"]);   // these have no check of their own
const isSlow = (name) => /nas|unifi|udm/i.test(name || "");

const db = new sqlite3.Database(dbPath, dryRun ? sqlite3.OPEN_READONLY : sqlite3.OPEN_READWRITE, (err) => {
    if (err) { console.error("cannot open " + dbPath + ": " + err.message); process.exit(1); }
});
const all = (sql, p = []) => new Promise((res, rej) => db.all(sql, p, (e, r) => (e ? rej(e) : res(r))));
const run = (sql, p = []) => new Promise((res, rej) => db.run(sql, p, (e) => (e ? rej(e) : res())));
const cols = 'id, name, type, "interval" AS int, retry_interval AS retry, maxretries AS tries, timeout';
const show = (rows) => rows.forEach((r) => console.log(
    `  #${String(r.id).padEnd(3)} ${String(r.name).trim().padEnd(20)} ${String(r.type).padEnd(8)} every ${String(r.int).padStart(3)}s  retry ${String(r.retry).padStart(3)}s  retries ${r.tries}  timeout ${r.timeout}s`));

(async () => {
    const monitors = (await all(`SELECT ${cols} FROM monitor ORDER BY id`)).filter((m) => !SKIP_TYPES.has(m.type));
    console.log(`${dryRun ? "DRY RUN: " : ""}${monitors.length} monitors with their own check. Before:`);
    show(monitors);
    if (dryRun) {
        console.log("\nWould set:");
        monitors.forEach((m) => { const t = isSlow(m.name) ? SLOW : FAST;
            console.log(`  #${String(m.id).padEnd(3)} ${String(m.name).trim().padEnd(20)} -> every ${t.interval}s, retry ${t.retry_interval}s, retries ${t.maxretries}, timeout ${t.timeout}s`); });
        return db.close();
    }
    await run("BEGIN");
    try {
        for (const m of monitors) {
            const t = isSlow(m.name) ? SLOW : FAST;
            await run('UPDATE monitor SET "interval" = ?, retry_interval = ?, maxretries = ?, timeout = ? WHERE id = ?',
                      [t.interval, t.retry_interval, t.maxretries, t.timeout, m.id]);
        }
        await run("COMMIT");
    } catch (e) { await run("ROLLBACK"); throw e; }
    console.log("\nAfter:");
    show((await all(`SELECT ${cols} FROM monitor ORDER BY id`)).filter((m) => !SKIP_TYPES.has(m.type)));
    db.close();
})().catch((e) => { console.error("failed: " + e.message); process.exit(1); });

/* Commands (on the Docker host; the repo is checked out at /opt/monitoring-repo/repo):
   docker run --rm -v monitoring_uptime-kuma-data:/app/data:ro -v /opt/monitoring-repo/repo/tools/kuma-tune.js:/app/tune.js:ro \
     --entrypoint node -w /app louislam/uptime-kuma:2.5.6 /app/tune.js --dry-run
*/
