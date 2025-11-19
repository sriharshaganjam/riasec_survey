/***** Google Form Response Tracker + Auto-Reminders (Updated) *****
 * Sheets it will manage:
 *  - "Email Tracker"   : Your master list of recipients
 *  - "Config"          : Settings (form link, reminder timing, etc.)
 *  - "Form Responses 1": The Form-linked sheet (created by Google Form)
 *
 * Menu:
 *   Form Tracker ▸ ① Setup (create tabs & headers)
 *                ▸ Update Now (mark responders)
 *                ▸ Send Reminders Now
 *                ▸ Send Reminders Now (Force)
 *                ▸ Reset Reminder Gates (Non-responders)
 *                ▸ Install Time Triggers
 *                ▸ Remove Triggers
 *
 * Key updates in this version:
 *  - DRY_RUN no longer updates Last Reminder Sent / Reminder Count
 *  - Config values are trimmed to avoid hidden whitespace bugs
 *  - FORCE_SEND config + menu option to override spacing/count/time windows
 *  - Debug logging explains why each row is skipped
 *******************************************************************/

const SHEET_TRACKER = "Email Tracker";
const SHEET_CONFIG  = "Config";
const SHEET_FORM    = "Form Responses 1"; // Change if your responses tab has a different name

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Form Tracker")
    .addItem("① Setup (create tabs & headers)", "setupTemplate")
    .addSeparator()
    .addItem("Update Now (mark responders)", "updateResponses")
    .addItem("Send Reminders Now", "sendReminders")
    .addItem("Send Reminders Now (Force)", "sendRemindersForce")
    .addItem("Reset Reminder Gates (Non-responders)", "resetReminderGatesForNonResponders")
    .addSeparator()
    .addItem("Install Time Triggers", "installTriggers")
    .addItem("Remove Triggers", "removeTriggers")
    .addToUi();
}

function setupTemplate() {
  const ss = SpreadsheetApp.getActive();

  // Email Tracker
  let tracker = ss.getSheetByName(SHEET_TRACKER);
  if (!tracker) tracker = ss.insertSheet(SHEET_TRACKER);
  tracker.clear();
  tracker.getRange(1,1,1,8).setValues([[
    "Name", "Email", "Responded?", "Response Timestamp",
    "Last Reminder Sent", "Reminder Count", "Opt-out?", "Custom Message"
  ]]);
  tracker.setFrozenRows(1);

  // Config
  let cfg = ss.getSheetByName(SHEET_CONFIG);
  if (!cfg) cfg = ss.insertSheet(SHEET_CONFIG);
  cfg.clear();
  cfg.getRange(1,1,12,2).setValues([
    ["Key","Value"],
    ["FORM_LINK","<< paste your Google Form link here >>"],
    ["REMINDER_SUBJECT","Gentle Reminder: Please complete the form"],
    ["REMINDER_BODY","Hi {{name}},\n\nThis is a friendly reminder to fill out the form:\n{{form_link}}\n\nThanks!"],
    ["REMINDER_DAYS_BETWEEN","3"],             // min days between reminders for the same person
    ["SEND_WINDOW_START_HOUR","9"],            // 24h
    ["SEND_WINDOW_END_HOUR","18"],             // 24h (exclusive)
    ["SEND_WEEKDAYS","Mon,Tue,Wed,Thu,Fri"],   // allowed weekdays
    ["ONLY_ONE_REMINDER","FALSE"],             // TRUE = send only once per person
    ["DRY_RUN","FALSE"],                       // TRUE = simulate (no emails)
    ["FORCE_SEND","FALSE"],                    // TRUE = ignore spacing/count/time window for next manual run
    ["TIMEZONE_NOTE","Set Apps Script Project Settings timezone to your local (e.g., Asia/Kolkata)"]
  ]);
  cfg.setFrozenRows(1);

  SpreadsheetApp.getUi().alert(
    "Setup complete ✅\n\n1) Paste your Form link in Config.\n2) Add recipients in Email Tracker.\n3) Link your Form to this Sheet (Responses → Link to Sheets)."
  );
}

function getConfigMap_() {
  const ss = SpreadsheetApp.getActive();
  const cfg = ss.getSheetByName(SHEET_CONFIG);
  if (!cfg) throw new Error("Config sheet not found. Run Setup first.");
  const data = cfg.getDataRange().getValues();
  const map = {};
  for (let i=1;i<data.length;i++){
    const k = (data[i][0] ?? "").toString().trim();
    const v = (data[i][1] ?? "").toString().trim(); // <-- trim values to avoid "FALSE " issues
    if (k) map[k]=v;
  }
  return map;
}

function hoursOk_(cfg) {
  const start = parseInt(cfg["SEND_WINDOW_START_HOUR"] || "0", 10);
  const end   = parseInt(cfg["SEND_WINDOW_END_HOUR"] || "23", 10);
  const now = new Date();
  const h = now.getHours(); // project timezone
  return h >= start && h < end; // end is exclusive
}

function weekdayOk_(cfg) {
  const allow = (cfg["SEND_WEEKDAYS"]||"Mon,Tue,Wed,Thu,Fri")
    .split(",").map(s=>s.trim().toLowerCase()).filter(Boolean);
  const wd = ["sun","mon","tue","wed","thu","fri","sat"][new Date().getDay()];
  return allow.includes(wd);
}

function updateResponses() {
  const ss = SpreadsheetApp.getActive();

  const tracker = ss.getSheetByName(SHEET_TRACKER);
  if (!tracker) throw new Error("Missing 'Email Tracker'. Run Setup first.");
  const formSheet = ss.getSheetByName(SHEET_FORM);
  if (!formSheet) throw new Error("Missing form responses tab. Link your Form to this Sheet.");

  const tVals = tracker.getDataRange().getValues();
  if (tVals.length < 2) return; // no recipients
  const tHeader = tVals[0];
  const tIdx = {
    name: tHeader.indexOf("Name"),
    email: tHeader.indexOf("Email"),
    responded: tHeader.indexOf("Responded?"),
    ts: tHeader.indexOf("Response Timestamp")
  };
  if (Object.values(tIdx).some(i=>i<0)) throw new Error("Email Tracker header mismatch. Run Setup again.");

  const fVals = formSheet.getDataRange().getValues();
  const fHeader = fVals[0];
  const emailColForm = fHeader.indexOf("Email") >= 0 ? fHeader.indexOf("Email") : fHeader.indexOf("Email Address");
  if (emailColForm < 0) throw new Error("Your Form must collect email addresses (column named 'Email' or 'Email Address').");

  // Map email -> first timestamp
  const respondedMap = new Map();
  for (let r=1;r<fVals.length;r++){
    const email = (fVals[r][emailColForm]||"").toString().trim().toLowerCase();
    if (!email) continue;
    if (!respondedMap.has(email)) respondedMap.set(email, fVals[r][0]); // col 0 is Timestamp
  }

  const out = [];
  out.push(tVals[0]);
  for (let i=1;i<tVals.length;i++){
    const row = tVals[i].slice();
    const email = (row[tIdx.email]||"").toString().trim().toLowerCase();
    if (!email) { out.push(row); continue; }
    if (respondedMap.has(email)) {
      row[tIdx.responded] = "Yes";
      row[tIdx.ts] = respondedMap.get(email);
    } else {
      row[tIdx.responded] = "No";
      row[tIdx.ts] = "";
    }
    out.push(row);
  }
  tracker.clearContents();
  tracker.getRange(1,1,out.length,out[0].length).setValues(out);
}

/**
 * Public entry: normal send respecting Config gates.
 */
function sendReminders() {
  sendRemindersInternal_(/*forceSend*/ false);
}

/**
 * Public entry: force send (ignores spacing, count, and time/weekday windows).
 * Also temporarily toggles FORCE_SEND=TRUE for this call only (does not persist).
 */
function sendRemindersForce() {
  sendRemindersInternal_(/*forceSend*/ true);
}

/**
 * Core sender with a force flag.
 * - When forceSend = true:
 *   - Ignores ONLY_ONE_REMINDER gate
 *   - Ignores REMINDER_DAYS_BETWEEN gate
 *   - Ignores SEND_WINDOW_* and SEND_WEEKDAYS gates
 */
function sendRemindersInternal_(forceSend) {
  const cfg = getConfigMap_();
  const ss = SpreadsheetApp.getActive();
  const tracker = ss.getSheetByName(SHEET_TRACKER);
  if (!tracker) throw new Error("Missing 'Email Tracker'. Run Setup first.");

  const tVals = tracker.getDataRange().getValues();
  if (tVals.length < 2) { Logger.log("No recipients in Email Tracker."); return; }
  const h = tVals[0];
  const idx = {
    name: h.indexOf("Name"),
    email: h.indexOf("Email"),
    responded: h.indexOf("Responded?"),
    ts: h.indexOf("Response Timestamp"),
    lastRem: h.indexOf("Last Reminder Sent"),
    remCount: h.indexOf("Reminder Count"),
    optOut: h.indexOf("Opt-out?"),
    custom: h.indexOf("Custom Message")
  };
  if (Object.values(idx).some(i=>i<0)) throw new Error("Email Tracker header mismatch. Run Setup again.");

  const formLink = (cfg["FORM_LINK"]||"").trim();
  if (!formLink || formLink.startsWith("<<")) throw new Error("Please set FORM_LINK in Config.");

  const onlyOnce = (cfg["ONLY_ONE_REMINDER"]||"FALSE").toUpperCase()==="TRUE";
  const dryRun   = (cfg["DRY_RUN"]||"FALSE").toUpperCase()==="TRUE";

  const minDays = Math.max(0, parseInt(cfg["REMINDER_DAYS_BETWEEN"]||"3",10));
  const subject = (cfg["REMINDER_SUBJECT"]||"Reminder: Please complete the form");
  const bodyTpl = (cfg["REMINDER_BODY"]||"Hi {{name}},\n\nPlease fill the form:\n{{form_link}}\n\nThanks!");

  // Respect quiet hours / weekdays unless forcing
  if (!forceSend) {
    if (!hoursOk_(cfg)) { Logger.log("Skipped: outside SEND_WINDOW hours."); return; }
    if (!weekdayOk_(cfg)) { Logger.log("Skipped: day not in SEND_WEEKDAYS."); return; }
  }

  let sent = 0;
  for (let i=1;i<tVals.length;i++){
    const row = tVals[i];
    const email = (row[idx.email]||"").toString().trim();
    const name = (row[idx.name]||"").toString().trim();
    const responded = (row[idx.responded]||"").toString().trim().toLowerCase() === "yes";
    const opted = (row[idx.optOut]||"").toString().trim().toUpperCase()==="TRUE";
    const custom = (row[idx.custom]||"").toString();
    const lastRemDate = row[idx.lastRem] ? new Date(row[idx.lastRem]) : null;
    const remCount = parseInt(row[idx.remCount]||"0",10);

    if (!email) { Logger.log(`Row ${i+1}: no email`); continue; }
    if (opted) { Logger.log(`Row ${i+1} (${email}): opted out`); continue; }
    if (responded) { Logger.log(`Row ${i+1} (${email}): already responded`); continue; }

    if (!forceSend && onlyOnce && remCount >= 1) {
      Logger.log(`Row ${i+1} (${email}): ONLY_ONE_REMINDER gate (count=${remCount})`);
      continue;
    }

    if (!forceSend && lastRemDate) {
      const daysSince = (Date.now() - lastRemDate.getTime())/(1000*60*60*24);
      if (daysSince < minDays) {
        Logger.log(`Row ${i+1} (${email}): ${daysSince.toFixed(2)}d since last < ${minDays}d`);
        continue;
      }
    }

    const msg = (custom && custom.trim().length>0) ? custom : bodyTpl;
    const body = msg
      .replaceAll("{{name}}", name || "there")
      .replaceAll("{{form_link}}", formLink);

    if (dryRun) {
      Logger.log(`[DRY_RUN] Would email → ${email}`);
      // Do NOT mutate date/count in DRY_RUN
    } else {
      GmailApp.sendEmail(email, subject, body);
      tracker.getRange(i+1, idx.lastRem+1).setValue(new Date());
      tracker.getRange(i+1, idx.remCount+1).setValue(remCount+1);
      Logger.log(`Email sent → ${email}`);
    }
    sent++;
  }
  Logger.log(`Reminders processed: ${sent}${dryRun ? " (dry run)" : ""}`);
}

function installTriggers() {
  removeTriggers(); // avoid duplicates

  // Keep responses fresh (hourly)
  ScriptApp.newTrigger("updateResponses")
    .timeBased().everyHours(1).create();

  // Daily reminder at 10:00 (adjust here if you want)
  ScriptApp.newTrigger("sendReminders")
    .timeBased()
    .atHour(10)        // 0–23
    .everyDays(1)
    .create();

  SpreadsheetApp.getUi().alert(
    "Installed triggers ✅\n- updateResponses(): hourly\n- sendReminders(): daily @10:00\n\n" +
    "Note: The function itself still checks Config for allowed weekdays/hours unless you use the Force menu."
  );
}

function removeTriggers() {
  const all = ScriptApp.getProjectTriggers();
  all.forEach(t => ScriptApp.deleteTrigger(t));
  SpreadsheetApp.getUi().alert("All triggers removed.");
}

/**
 * Clears spacing/count gates ONLY for non-responders.
 * Handy if you want normal (non-force) runs to be eligible again without losing history for responders.
 */
function resetReminderGatesForNonResponders() {
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheetByName(SHEET_TRACKER);
  if (!sheet) throw new Error("Missing 'Email Tracker'.");
  const data = sheet.getDataRange().getValues();
  const h = data[0];
  const idx = {
    responded: h.indexOf("Responded?"),
    lastRem: h.indexOf("Last Reminder Sent"),
    remCount: h.indexOf("Reminder Count")
  };
  if (Object.values(idx).some(i=>i<0)) throw new Error("Email Tracker header mismatch.");

  let cleared = 0;
  for (let r=1; r<data.length; r++) {
    const responded = (data[r][idx.responded] || "").toString().trim().toLowerCase() === "yes";
    if (!responded) {
      sheet.getRange(r+1, idx.lastRem+1).clearContent();
      sheet.getRange(r+1, idx.remCount+1).setValue(0);
      cleared++;
    }
  }
  SpreadsheetApp.getUi().alert(`Reset complete ✅\nRows updated (non-responders): ${cleared}`);
}
