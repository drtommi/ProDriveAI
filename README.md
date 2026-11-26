# ProDriveAI

An independent, unofficial personal MCP server for moving files between ChatGPT, Codex or an MCP-capable agent and the **ProDriveAI** folder in Proton Drive. It runs on a desktop you control. Each new transfer or listing opens a local approval dialog, including listing filenames. A missing desktop, a declined request, or a 40-second timeout denies the operation. Each connection uses the Proton account signed into the desktop CLI.

## Set up the host

1. Install Node.js 22 or later, Python 3 with Tk, and the official Proton Drive CLI. Verify the CLI download against Proton's published SHA-512. The connector was developed against the 0.9.0 CLI command interface. [Official download](https://proton.me/download/drive/cli/index.html)
2. Run `proton-drive auth login` on that computer and sign in in your browser. Create a **ProDriveAI** folder directly under **My files** in Drive. Verify with `proton-drive filesystem list "/my-files/ProDriveAI"`. Use your OS keychain. On Linux, run in the desktop session with its keyring unlocked. [Proton CLI documentation](https://github.com/ProtonDriveApps/sdk/blob/main/cli/README.md)
3. Unzip the connector into a directory under your control and run `npm ci --ignore-scripts` there. Run `python3 -m tkinter` to verify the desktop can display the approval window. On Windows, set APPROVAL_PYTHON to the absolute path to python.exe. Set DRIVE_CLI to the absolute path of the official CLI executable.
4. Set `DRIVE_ALLOW_CREATE=1` for uploads and folder creation. Set `DRIVE_ALLOW_MANAGE=1` to enable file renaming, moving, and deletion to Trash. Each permission is independent. Restart the connection after changing the environment. Both groups of tools require desktop approval.

On Windows, deploy the runtime code and its Node and Python dependencies to an administrator-controlled directory such as `%ProgramFiles%\ProDriveAI`. Configure the tunnel and Codex to launch this installed copy with absolute executable paths. Keep the development checkout separate. Keep tunnel credentials, launcher settings, and the Proton keychain in the signed-in user's profile.

## Manage files

The management tools accept paths relative to the **ProDriveAI** folder, including files in existing subfolders. Separate folder names with `/`. Each call acts on one regular file. Example requests:

- **Rename** `Recordings/take.wav` to `interview.wav`. The `rename_file` tool keeps the file in the same folder.
- **Move** `Recordings/interview.wav` into `Archive/2026`. The `move_file` tool keeps the filename. Pass an empty `destinationFolder` to move a file back to the top-level ProDriveAI folder.
- **Delete** `Archive/2026/interview.wav`. The `delete_file` tool sends the file to Proton Drive Trash. You can restore it in Proton Drive.

To create a destination, ask **“Create a folder called Archive under ProDriveAI.”** The `create_folder` tool takes a plain `name` and an optional `parentFolder`. For example, use `{"name":"2026","parentFolder":"Archive"}` once Archive exists.

Reads, listings, and document searches continue to use files directly inside the top-level folder. To read a file you moved, move it back first. For the Windows sign-in launcher, set `$env:DRIVE_ALLOW_MANAGE = '1'` in the setup shell before saving the launcher settings. Refresh ChatGPT tool discovery after restarting the server.

## Document search and reading

For document tools, install Python 3.11 or later and set up their dependencies from the extracted package directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows, use `py -3 -m venv .venv` and `.venv\Scripts\python.exe -m pip install -r requirements.txt`. Set `PRODRIVEAI_PYTHON` in the MCP server environment to the absolute path of that virtual environment's Python executable. Keep `APPROVAL_PYTHON` pointed at your Tk-enabled Python. Install Tesseract and its English language data on the host for scanned PDFs. Its executable must be on the server's PATH. To use another installed language, set `PRODRIVEAI_OCR_LANG` to its Tesseract code. Search and extraction run locally. File transfer can run independently of these packages.

- Ask **“Search the contents of my PDFs, Word documents, and notes for ‘renewal date’. Show the filenames and matching passages.”** Each approved call scans a batch directly inside **ProDriveAI** in filename order. The default batch is four files. The server returns up to three snippets per matching file and a continuation cursor for the next batch. Skipped documents and page errors are identified separately. Results refer to folder contents at the time of the call. The server downloads the eligible documents on demand and keeps no persistent search index.
- Ask **“Read page 2 of Report.pdf”** or **“Extract the next passage from Terms.docx.”** Each approved excerpt defaults to 4,000 characters, with a maximum of 12,000. PDF page numbers start at one. DOCX and UTF-8 text use a character offset. Follow the returned continuation to read more.
- Searches use case-insensitive literal phrases, including in DOCX body paragraphs and tables. PDF extraction uses embedded text first. Pages without readable embedded text use local OCR when available. OCR accuracy depends on scan quality. Images embedded alongside readable PDF text, and images inside DOCX, are outside OCR coverage. Supported text extensions are TXT, MD, CSV, TSV, JSON and LOG.
- The existing file-size limit also applies to document tools. A slow or encrypted file can be reported as skipped. For a long scanned PDF, request individual pages. The local worker has a 45-second processing budget per document and reports failures to the caller.

If upgrading, point Codex or the tunnel launcher at the new `prodriveai/server.mjs`, set the plugin display name to **ProDriveAI**, restart the server and refresh tool discovery. If you used the previous folder, rename **Chat Exchange** to **ProDriveAI** in Proton Drive, or create **ProDriveAI** and move in only the files you want the connector to access.

## Local Codex

Add this to your Codex config.toml, replacing the paths with actual absolute paths. Use single-quoted TOML strings for Windows paths. Close and reopen Codex or reconnect the server. Run /mcp to check tool discovery.

```toml
[mcp_servers.prodriveai]
command = "/absolute/path/to/node"
args = ["/absolute/path/to/prodriveai/server.mjs"]
tool_timeout_sec = 120

[mcp_servers.prodriveai.env]
DRIVE_CLI = "/absolute/path/to/proton-drive"
APPROVAL_PYTHON = "/absolute/path/to/python3"
PRODRIVEAI_PYTHON = "/absolute/path/to/prodriveai/.venv/bin/python"
DRIVE_ALLOW_CREATE = "1"
DRIVE_ALLOW_MANAGE = "1"
```

Try “Use prodriveai to save the text 'hello' as hello.txt.” Approve the local prompt. Then ask “Use prodriveai to read hello.txt as text.” Decline once to verify the call fails, then repeat and approve. [Codex MCP configuration](https://developers.openai.com/codex/mcp/)

## ChatGPT and remote agents

Use a **single-user** OpenAI Secure MCP Tunnel. Anyone allowed to call this tunnel can trigger an approval dialog for the same Drive session. Keep access private to yourself. The dialog identifies the action and filename. It cannot authenticate the person who sent the request. Approve only actions you initiated. A shared deployment needs per-user authentication and isolated Proton sessions.

1. In OpenAI Platform tunnel settings, create or select a private tunnel associated with your intended workspace. Obtain a restricted runtime key with Tunnels Read + Use. Install OpenAI's tunnel-client on the signed-in desktop. Use its supported secret-input mechanism or set CONTROL_PLANE_API_KEY in the local environment. Keep credentials out of chat.
2. Configure the stdio backend to launch this package using absolute paths. Ensure the launched process receives DRIVE_CLI and, for uploads, DRIVE_ALLOW_CREATE=1. If the tunnel client filters environment variables, use a local launcher script that sets them and starts Node. Keep the runtime key out of that script. Example commands below assume paths without spaces and a POSIX shell.

   ```sh
   tunnel-client init --sample sample_mcp_stdio_local --profile prodriveai \
     --tunnel-id YOUR_TUNNEL_ID --mcp-command "/absolute/path/to/node /absolute/path/to/prodriveai/server.mjs"
   tunnel-client doctor --profile prodriveai --explain
   tunnel-client run --profile prodriveai
   ```
3. In ChatGPT on the web, open Plugins, choose **Add custom MCP server**, choose **Tunnel** and select the private tunnel. Keep the plugin private. Refresh tools after changing the write setting. In a chat, select the plugin with @ and ask “Save the attached invoice as invoice.pdf in ProDriveAI.” For the reverse direction, ask “Retrieve invoice.pdf as a file.” Text results can be read in chat. Binary results use an MCP embedded resource and include a download control for compatible ChatGPT hosts. Rendering depends on the client.
4. For a Responses API agent use an MCP tool definition with the same tunnel_id, tool allowlist, and approval policy, for example:

   ```json
   {"type":"mcp","server_label":"prodriveai","tunnel_id":"YOUR_TUNNEL_ID","allowed_tools":["list_files","read_file","read_file_part","extract_text","search_documents"],"require_approval":"always"}
   ```

ChatGPT custom-MCP write access depends on plan and workspace settings. OpenAI lists full support for Business and Enterprise/Edu, and read/fetch for Pro. Workspace Agents have separate per-agent action settings. Verify that the chosen client supports custom tools. [ChatGPT availability](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt) · [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) · [Agent tool approvals](https://developers.openai.com/api/docs/guides/tools-connectors-mcp)

## Data and limits

The official CLI uses Proton's Drive SDK for encryption, decryption and transfers. ChatGPT receives the decrypted content you approve. Binary tool results contain the original bytes in base64, which is reversible. The client's chat retention settings apply. An uploaded chat attachment has already been shared with ChatGPT. Temporary plaintext transfer files are removed on normal completion or handled errors. A forced shutdown can leave a temporary directory behind. Protect the desktop, OS keychain, CLI caches and temp storage.

ChatGPT attachment uploads (`save_attachment`) default to **100 MB** (100,000,000 bytes). A single direct write (`save_content`) accepts up to **10 MiB** (10,485,760 decoded bytes). The OpenAI tunnel limits the complete serialized request to 10 MiB, including JSON and any base64 encoding. Clients with access to the original bytes can use `begin_content_upload` and `save_content_part` for a direct write that exceeds one message. Approve the filename and total byte count once, then send the numbered parts in order. Base64-encode each part separately using the returned `partSize` in bytes. The final part creates the file. Tickets last ten minutes, and the server retains up to eight upload sessions at a time.

Downloads and document tools default to 10 MiB. To override the attachment, download, and document limits, set DRIVE_MAX_FILE_MB to a whole number from 1 to 100 in decimal MB and restart. A configured limit below 10 MiB also caps direct writes. Attachments stream to private temporary storage. Inline reads use a 1 MiB limit. For larger downloads use file format. A single approval creates a random bearer ticket for an in-memory snapshot, valid for ten minutes in the same server process. Keep the ticket private. The widget or an MCP client fetches zero-based parts in order. Decode each base64 part separately before joining the bytes. This delivers the original file for download. Large file contents do not automatically become model context. The server retains up to 200 MB of snapshots at a time. ChatGPT attachment availability, client support, connection speed and tunnel deadlines can impose smaller practical limits. Use UTF-8 text or standard padded base64 for save_content. Downloaded file resources are subject to client message and tunnel limits, so a client may accept less. save_attachment supports signed HTTPS URLs on files.oaiusercontent.com only and rejects redirects. Other file hosts fail closed. The connector accepts regular uploaded files. Export native Proton Docs and Sheets as ordinary files first. Keep the installed package and executable paths outside agent-writable directories. An agent with unrestricted shell and access to your OS keychain could use the CLI independently of these tool controls. Run such an agent under a separate OS identity or on a separate host.

To revoke access, stop the tunnel and remove the plugin or Codex MCP entry. Use proton-drive auth logout on the host to end the CLI session. Revocation affects future access. Proton describes third-party SDK integrations as suitable for personal, non-commercial projects at this stage. [SDK status and usage guidelines](https://github.com/ProtonDriveApps/sdk)
