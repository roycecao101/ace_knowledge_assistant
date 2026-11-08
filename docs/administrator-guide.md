# Ace Knowledge Assistant — Administrator’s Guide

For office managers and administrators. Covers the dashboard currently implemented in this project, reviewed November 8, 2026.

## 1. Sign in and check the workspace

Open `/admin-login.html` on your organization’s application site and sign in with your own administrator identifier and password. Use **Logout** when finished, especially on a shared computer.

Start with **Overview**:

- Check active employee and administrator totals.
- Check indexed-document and unreadable-file counts.
- Review knowledge health and the last successful synchronization.
- Follow any policy-discrepancy alert to **Find & Fix Log**.

The dashboard has six sections:

| Section | What you manage |
| --- | --- |
| Overview | Account totals, knowledge health, and review alerts |
| Employee Management | Employee accounts, home offices, PIN resets, and access |
| Knowledge Management | Drive connection, document inventory, unreadable files, re-sync, and folder settings |
| Office Management | Office directory and new offices |
| Admin Management | Administrator accounts, passwords, and access |
| Find & Fix Log | Potential policy discrepancies and verified source comparisons |

**Employee View** lets you check search using your administrator session. A screen marked **SYNTHETIC LOCAL PREVIEW** is a fictional preview; actions there do not change real accounts or documents.

## 2. Manage documents

### Add or update a document

1. Open the approved knowledge folder in Google Drive.
2. Add or edit the approved source document there. The application has no browser upload control.
3. Use a Google Doc, Word `.docx` file, or PDF with selectable text. Convert legacy `.doc` files and scanned documents to a supported, readable format.
4. Put the document in the appropriate configured category subfolder. Files at the approved root are available across categories.
5. Check office scope using the guidance below.
6. Open **Knowledge Management**, select **Re-sync now**, and confirm successful completion.
7. Check **Indexed Documents** and **Unreadable Files**, then test the result in **Employee View**.

Coordinate category-folder changes with the technical owner. The dashboard does not provide a category-folder mapping editor.

### Set the applicable offices

Use office codes at the beginning of office-specific filenames, followed by a dash:

- `ALP - Equipment Procedure.pdf` applies to Alpharetta.
- `ALP NOR - Equipment Procedure.pdf` applies to Alpharetta and Norcross.
- `LIL - Equipment Procedure.docx` or `ADC - Equipment Procedure.docx` applies to Lilburn.

These are naming examples, not actual policy documents. Unscoped content generally applies company-wide, so verify the displayed **Applicable office** after synchronization.

In Word and Google Docs, use styled headings for office-specific sections. An explicit heading such as `Norcross Emergency Action` can scope that section. Office codes also work at the beginning of styled headings, such as `ALP NOR - Emergency Action`. A section can narrow a filename’s office scope but cannot expand it. A passing mention of an office in normal text does not establish scope.

Home-office assignment sets an employee’s initial search office. Employees can select another search office; this assignment is not a separate restriction on which office they may search.

### Remove or replace an outdated document

1. Obtain the appropriate manager’s approval for the source change.
2. Remove the outdated file from the approved Drive inventory, or update the existing source. Keep any required archive outside the synchronized inventory.
3. Re-sync promptly.
4. Confirm the current inventory and test a related search.

Drive edits and deletions do not update the application until synchronization succeeds. A failed sync can leave the previous version searchable.

### Fix unreadable files

In **Knowledge Management → Unreadable Files**, review the filename and extraction failure. Unreadable files are excluded from search and discrepancy analysis.

Replace the source with a readable Google Doc, `.docx`, or text PDF, then re-sync. OCR is not implemented; a PDF containing image-only pages may fail even when other pages contain text. Complex Word textboxes and embedded objects may not be extracted. Verify important passages through Employee View after conversion.

## 3. Re-sync and connection settings

### Run a re-sync

1. Open **Knowledge Management**.
2. Check the source label. **Synthetic document source** or **Local source** indicates fictional development documents.
3. Select **Re-sync now**. It is disabled while synchronization is running or no folder is configured.
4. Watch the status, or select **Refresh status**.
5. Confirm that **Last successful sync** advances and review document counts and errors.
6. Check **Find & Fix Log**, then test a known approved passage in Employee View with the intended office and category.

A request being accepted does not mean synchronization has completed. Depending on deployment, the request may wait for a scheduler or operator. Automatic daily synchronization requires a configured, working executor. For the repository’s free Render demonstration setup, an operator must run synchronization manually; the dashboard request alone does not complete it. Ask the technical owner which arrangement your installation uses.

| Status or symptom | What to do |
| --- | --- |
| Folder not configured | Have the approved folder confirmed, then save its ID in Advanced Settings. |
| Not yet verified | Run a sync; saving an ID alone does not verify access. |
| Synchronization in progress | Wait and refresh; a sync can take several minutes. |
| Last synchronization completed | Check its timestamp, unreadable files, and a sample search. |
| Last synchronization failed | Read the error, check approved folder access, and retry. The prior index may remain available and be stale. |
| Request remains pending | Ask the technical owner to check the scheduler or manual executor. |

### Change the approved folder

Use **Knowledge Management → Advanced Settings → Google Drive folder ID** only when an approved folder change is intended.

1. Confirm the correct folder and authorized Google identity with the technical owner.
2. Copy the folder ID from its Drive address and select **Save folder ID**.
3. Re-sync and verify the inventory and office scopes.

Changing the folder clears active search results until a successful synchronization of the new folder. Folder settings cannot be edited during an active sync. Local OAuth installations may be pinned to a specific approved folder by the technical owner.

If **Connect Google Drive** is available, use the approved Google account for authorization, then re-sync. Other installations manage authorization on the server. Credential files, tokens, and passwords do not belong in the folder-ID field. Ask the technical owner to repair expired or revoked authorization.

## 4. Manage offices

Open **Office Management** to review office names, primary codes, and alternate codes.

| Office | Primary code | Alternate code |
| --- | --- | --- |
| Alpharetta | ALP | — |
| Norcross | NOR | — |
| Lilburn | LIL | ADC |

To add an office:

1. Select **Add office**.
2. Enter a unique office name and code. Codes require 2–10 letters or digits, begin with a letter, and are saved in uppercase.
3. Select **Save**.
4. Confirm the office appears in employee forms and search office selectors.
5. Update source filenames or styled headings where needed, then re-sync to apply the office scope to existing documents.

Codes cannot duplicate existing codes or aliases. Preserve Lilburn’s `ADC` alias. The current dashboard supports adding and viewing offices; contact the technical owner for an office rename, removal, or alias change.

## 5. Manage employees

### Create an employee

1. Open **Employee Management → Create employee**.
2. Enter a unique **Account identifier**, **Display name**, and **Home office**.
3. Select **Save**.
4. Deliver the generated one-time PIN privately to the employee, along with their identifier and employee sign-in address (`/login.html`).

The PIN cannot be retrieved later. Its dialog clears when closed, when the tab is hidden, or after 60 seconds. If it is missed, use **Reset PIN**. Do not place PINs in shared documents or support tickets.

### Edit details or reset access

- Use the search box to find an employee by name, identifier, office, or status.
- Select **Edit employee** to change their display name or home office, then **Save**. Editing details invalidates existing sessions; the employee must sign in again.
- Select **Reset PIN** to generate a replacement PIN. The old PIN and existing sessions stop working. Deliver the new PIN privately.
- Select **Deactivate**, check the name and identifier, and confirm **Deactivate account** to end access immediately. The home-office assignment is retained.
- Select **Reactivate** only after access has been authorized again. Reset the PIN if a fresh credential is needed; reactivation itself does not generate one.

An employee account and an administrator account are separate. If someone has both, manage both records.

## 6. Manage administrators

### Add an administrator

1. Open **Admin Management → Add administrator**.
2. Enter a unique identifier, display name, and password of at least 12 characters.
3. Select **Save**, then privately provide the sign-in details and `/admin-login.html` address.
4. Have the new administrator confirm that they can sign in before relying on that account for a handover.

Use named individual accounts so responsibilities and access can be handed over clearly.

### Change a password or deactivate an administrator

Select **Change password**, enter a replacement password of at least 12 characters, and save. Password replacement invalidates that account’s existing sessions.

Select **Deactivate**, confirm the correct person, and choose **Deactivate account**. Existing sessions end immediately. **Reactivate** restores the account’s active status when authorized.

At least **two active administrators must remain**. When only two are active, deactivation is disabled. Add or reactivate an authorized replacement and verify their login before deactivating a departing administrator. Have a remaining administrator complete and verify the departure.

## 7. Review the Find & Fix Log

1. Open **Find & Fix Log** and check the scan status and last successful scan.
2. Open **View details** for an issue marked **Needs Review**.
3. Compare both exact verified quotations, filenames, headings/pages, and applicable offices. Use **Previous comparison** and **Next comparison** when additional evidence is available.
4. Ask the responsible manager to review the original documents and decide which policy applies.
5. Correct or remove the outdated source in Google Drive after approval.
6. Re-sync, reopen the log, and check the affected employee search.

The app does not choose the correct policy or edit source documents. There is no manual “mark resolved” control; the next successful analysis reflects source corrections. A successful empty scan means no supported discrepancies were found, not that every policy agrees. **Unavailable**, **Analysis incomplete**, **Scan failed**, or **Awaiting analysis** requires follow-up rather than treating the log as clear.

## 8. Cost and operational settings

There is **no Cost Settings or Billing section** in the current dashboard. Advanced Settings contains the approved Drive folder ID. Hosting plans, database plans, billing alerts, spending limits, backup retention, and synchronization scheduling are managed outside the app by the technical owner.

Document extraction, search, quotation verification, and discrepancy analysis run locally without an external AI service. The application has no AI model selection, API-credit balance, or per-question cost control. Hosting, storage, database, and connected-service costs depend on the deployment.

For a cost review, have the technical owner record:

- The owners of the hosting, database, Google project, and billing accounts.
- Approved plans, budget, and any provider alerts or spending controls actually configured.
- Whether synchronization is scheduled or requires a manual operator.
- Backup/retention arrangements and any resource-expiration dates.
- Who approves plan changes and who retires unused resources.

Do not assume the dashboard enforces a spending cap or that every installation is free. The [Render demonstration guide](render-deployment.md) describes that specific setup and its constraints; confirm live pricing and account settings with the providers before approving spending.

## 9. Offboarding checklist

Complete this at the authorized departure time. Record completion in your organization’s access checklist or ticket; the application does not provide an offboarding workflow.

Person: ____________________  Departure time: ____________________

Responsible administrator: ____________________  Reference: ____________________

### Application access

- [ ] Identify every employee and administrator account belonging to the person; check identifiers as well as names.
- [ ] If they are an administrator, confirm two authorized active administrators will remain. Add and verify a replacement first when needed.
- [ ] In **Employee Management**, deactivate each relevant employee account and confirm **Inactive**.
- [ ] In **Admin Management**, deactivate each relevant administrator account and confirm **Inactive**. A remaining administrator verifies the result.
- [ ] Confirm that all identified application accounts are inactive. Deactivation invalidates existing sessions and blocks new authenticated access.
- [ ] Record the account identifiers, completion time, and person who performed the checks. Do not record PINs or passwords.

### Google Drive and infrastructure access — coordinate with the technical owner

- [ ] Remove the person’s direct and group-based access to the approved Drive folder and other relevant organizational resources.
- [ ] Transfer ownership or management of approved documents and folders to an authorized organizational owner where needed.
- [ ] If the connected Google identity belongs to the departing person, arrange replacement authorization and verify a successful sync as part of the handover.
- [ ] Remove access to hosting, database, Google Cloud/OAuth configuration, source repository, deployment tools, backups, secret storage, and billing accounts as applicable.
- [ ] Replace shared credentials or secrets the person knew where required by your access policy. Coordinate changes so the application and synchronization can continue operating.
- [ ] Transfer pending document corrections, Find & Fix issues, manual-sync duties, and billing/renewal responsibilities to named owners.

Deactivating an application account does not revoke Google or infrastructure access. Removing Drive access does not immediately remove an already indexed document from employee search.

### Verify the handover

- [ ] Re-sync if document ownership, approved inventory, permissions, or the connected identity changed. Confirm a new successful-sync timestamp and review errors.
- [ ] Test an approved passage in **Employee View**, using the intended office and category.
- [ ] Review **Unreadable Files** and **Find & Fix Log** for follow-up work.
- [ ] Confirm at least two active administrators remain and the ongoing technical owner has the required access.
- [ ] Retain account and business records under the organization’s retention policy. Deactivation retains account records; it does not erase documents or backups.
- [ ] Mark the checklist complete and assign any outstanding work to an owner and due date.

## 10. Routine checks and support

After source changes, check the successful-sync timestamp, inventory, unreadable files, discrepancy log, and a sample employee search. Periodically review active accounts, office assignments, the two-admin minimum, and the technical owner’s access and cost records.

If a sync or search problem persists, give the technical owner the time, affected dashboard section, status/error, and a safe description of the problem. Keep credential files, tokens, PINs, confidential policy text, patient information, and employee questions out of support tickets and screenshots. Questions and answers are not stored by the application, so there is no individual question-history report to review during offboarding.
