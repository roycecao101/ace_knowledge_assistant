"""Local operator login and metadata-only preflight; never downloads documents."""
import argparse
import json
import logging
from .drive_auth import (DRIVE_SCOPES, DriveAuthError, OAuthStore, build_service,
                         check_account, quiet_google_logging)


def login(store):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_config(store.client_config(), scopes=DRIVE_SCOPES,
                                             autogenerate_code_verifier=True)
    credentials = flow.run_local_server(
        host='127.0.0.1', port=0, open_browser=True, timeout_seconds=180,
        authorization_prompt_message='',
        success_message='Authorization received. You may close this window and return to the terminal.',
        access_type='offline', prompt='consent', login_hint=store.email,
        include_granted_scopes='false')
    if not credentials.refresh_token or set(credentials.granted_scopes or credentials.scopes) != set(DRIVE_SCOPES):
        raise DriveAuthError('Consent must grant only Drive read-only access and include offline access. Repeat login.')
    check_account(build_service(credentials), store.email)
    store.save(credentials)  # Each login invalidates the previous verification receipt.


def verify(store):
    from .drive_client import DriveClient
    credentials = store.load(require_verified=False)
    service = build_service(credentials)
    check_account(service, store.email)
    client = DriveClient(service)
    inventory = client.inventory(store.folder)
    # JSON escaping keeps filenames from injecting terminal control sequences.
    print(json.dumps({'folder_id': store.folder, 'files': [
        dict(file_id=f.id, filename=f.name, mime_type=f.mime, modified=f.modified,
             category=f.category, downloadable=f.downloadable) for f in inventory]}, indent=2, ensure_ascii=True))
    store.save(credentials, verified=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['login', 'verify'])
    args = parser.parse_args(argv)
    quiet_google_logging()
    # Suppress library logging even if a caller enabled HTTP/OAuth debug loggers.
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        store = OAuthStore.configured()
        if args.action == 'login':
            login(store)
            print('Local authorization saved. Run python -m backend.drive_oauth verify before synchronization.')
        else:
            verify(store)
            print('Metadata verification succeeded. No documents were downloaded or imported.')
        return 0
    except DriveAuthError as exc:
        print(str(exc))
        return 1
    except Exception:
        # OAuth/transport exceptions may contain tokens, codes or private URLs.
        print('Google authorization or metadata verification failed. Check private file permissions, team account, folder access, API approval, and consent; retry login if needed.')
        return 1
    finally:
        logging.disable(previous)


if __name__ == '__main__':
    raise SystemExit(main())
