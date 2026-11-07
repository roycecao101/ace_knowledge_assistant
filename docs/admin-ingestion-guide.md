# Miriam's document guide

Sign in through the administrator login with your own administrator account. Your technical owner connects the approved Google service identity once; you never need to enter a credential file, run code, or renew a certificate.

To connect a knowledge folder, open **Google Drive Synchronization** or **Settings**, paste the folder ID from its Google Drive address into **Google Drive folder ID**, and save. Use only the approved Ace knowledge folder. Changing folders clears the old search results until the next successful synchronization.

Add and edit documents in Google Drive. Supported sources are Google Docs, Word `.docx` files, and PDFs with selectable text. Put them in the approved category subfolders or at the top level to include them in every category. Prefix office-specific filenames with codes followed by a dash, for example `ALP NOR - Equipment Procedure.pdf`. Use `ADC` or `LIL` for Lilburn. In Word and Google Docs, styled headings such as `Norcross Emergency Action` apply to their sections until the next heading at the same level. Unlabelled passages apply company-wide. Merely mentioning Affordable Dental Care does not make a passage Lilburn-only.

Select **Re-sync now**, then **Refresh status**. A sync can take several minutes. Check the **Last successful synchronization** time and the document list. New, modified, renamed, moved, and deleted documents are reflected after success. Automatic synchronization also runs daily while the application is online. Always synchronize promptly after removing an outdated policy.

Open **Files I could not read** to review filenames and extraction errors. Scanned images cannot be read yet. Replace them in Drive with a text PDF, Word document, or Google Doc and synchronize again. Do not upload documents into the tool; it reads them only from Drive.

If synchronization reports failure, the previous search index remains available and may be out of date. Check that the folder still exists and that its service account still has Viewer access, then retry. If it still fails, contact your technical owner with the time and dashboard error. Do not send policy text or employee questions in the support request.

Test a successful sync in **Employee View**: choose the intended office and category and search for a distinctive phrase from an approved document. Each result should show its exact filename, page or heading, and office label. If nothing supports the question, the tool says it could not find it. If matching passages disagree, ask a manager which applies. The current lexical search can miss paraphrases and does not recognize every type of contradiction.

The existing Employee Management and Admin Management screens retain their access controls. Document ingestion does not add office management or Policy Pulse; those sections still report unconnected.
