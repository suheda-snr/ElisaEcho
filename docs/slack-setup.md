# Connecting Slack to Elisa Echo – step by step

This guide connects a **Slack test workspace** to Elisa Echo so that knowledge is discovered
automatically from real conversations. It takes about 15 minutes. You need permission to install
apps in the Slack workspace (use your own free test workspace if you are unsure).

**What you will end up with:** two tokens in `backend/.env`, a monitored channel, and the
Integrations page showing **Connected**.

---

## Fast path (about 5 minutes): create the app from the manifest

The file [`slack-app-manifest.yaml`](slack-app-manifest.yaml) already contains everything from
steps 2–5 below (Socket Mode, the three read-only scopes, the `message.channels` event).

1. Open <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick your **test workspace** → **Next**.
3. Choose **YAML**, delete the example, paste the whole content of
   `docs/slack-app-manifest.yaml` → **Next** → **Create**.
4. **App token:** **Basic Information** → **App-Level Tokens** → **Generate Token and Scopes**
   → name `elisa-echo-socket`, add scope `connections:write` → **Generate** → copy the `xapp-…`
   token (`SLACK_APP_TOKEN`).
5. **Bot token:** **Install App** → **Install to Workspace** → **Allow** → copy the
   **Bot User OAuth Token** `xoxb-…` (`SLACK_BOT_TOKEN`).
6. Continue with **Step 7** below (invite the app to the channel), then steps 8–12.

The manual steps 2–6 below do the same thing by hand.

---

## Step 1 – Have a Slack workspace

Use a test workspace, not your company's production Slack.

- No workspace yet? Create one for free at <https://slack.com/get-started> → *Create a new
  workspace*.
- Create a channel for the demo, for example **`#noc-test`** (public channel).
- For the demo conversation you need **two people** (or two accounts) in that channel:
  "Engineer A" and "Engineer B".

---

## Step 2 – Create the Slack app

1. Open <https://api.slack.com/apps> and sign in.
2. Click **Create New App** → **From scratch**.
3. **App Name:** `Elisa Echo` (any name works).
4. **Pick a workspace:** your test workspace.
5. Click **Create App**. You land on the app's **Basic Information** page.

---

## Step 3 – Turn on Socket Mode and get the App token (`xapp-…`)

Socket Mode lets Elisa Echo receive messages without a public web address.

1. In the left menu, under **Settings**, click **Socket Mode**.
2. Switch **Enable Socket Mode** on.
3. Slack asks you to create an **app-level token**:
   - **Token Name:** `elisa-echo-socket`
   - **Scope:** `connections:write` (already selected)
   - Click **Generate**.
4. Copy the token that starts with **`xapp-`**. This is your **`SLACK_APP_TOKEN`**.

> Lost it? **Basic Information** → **App-Level Tokens** → click the token name to see it again.

---

## Step 4 – Give the bot read permissions (scopes)

1. Left menu → **OAuth & Permissions**.
2. Scroll to **Scopes** → **Bot Token Scopes** → **Add an OAuth Scope**, and add exactly these three:

   | Scope | Why Elisa Echo needs it |
   |---|---|
   | `channels:history` | Read messages in public channels the app has been invited to |
   | `channels:read` | Show channel names on the Integrations page |
   | `users:read` | Show the real author name next to each message |

Do **not** add DM, private-channel or write scopes. Elisa Echo only reads.

---

## Step 5 – Subscribe to message events

1. Left menu → **Event Subscriptions**.
2. Switch **Enable Events** on. (With Socket Mode on, no Request URL is needed.)
3. Open **Subscribe to bot events** → **Add Bot User Event** → choose **`message.channels`**.
4. Click **Save Changes** at the bottom.

---

## Step 6 – Install the app and get the Bot token (`xoxb-…`)

1. Left menu → **Install App** (or **OAuth & Permissions** → **Install to Workspace**).
2. Click **Install to Workspace** → **Allow**.
3. Copy the **Bot User OAuth Token** that starts with **`xoxb-`**. This is your
   **`SLACK_BOT_TOKEN`**.

> If you change scopes or events later, Slack shows a yellow banner asking you to **reinstall**
> the app. Do it, otherwise the change has no effect.

---

## Step 7 – Invite the app to the channel and copy the channel ID

1. In Slack, open **`#noc-test`** and type:

   ```text
   /invite @Elisa Echo
   ```

   (Use your app's name.) Slack confirms that the app was added. The app only sees channels it
   has been invited to.
2. Get the **channel ID**: click the channel name at the top → **About** (or *View channel
   details*) → at the bottom you see **Channel ID**, e.g. `C0123456789`. Copy it. You need it in the
   next step or on the Integrations page.

---

## Step 8 – Put the tokens in `backend/.env`

Open `backend/.env` (not `frontend/.env`!) and add:

```env
SLACK_ENABLED=true
SLACK_BOT_TOKEN=xoxb-paste-your-bot-token-here
SLACK_APP_TOKEN=xapp-paste-your-app-token-here
# Optional: start monitoring this channel automatically
SLACK_CHANNEL_IDS=C0123456789
```

- No quotes and no spaces around `=`.
- `backend/.env` is ignored by Git, so the tokens are never committed. Never paste tokens into
  chat, tickets or `frontend/.env`.
- `SLACK_SIGNING_SECRET` is **not** needed (it is only for webhook mode).

---

## Step 9 – Restart the backend and the Slack worker

From the project folder:

```bash
docker compose up -d --force-recreate backend slack-worker
```

Check the worker log (press `Ctrl+C` to stop watching):

```bash
docker compose logs -f slack-worker
```

You should see: `Connected to Slack workspace <your workspace> via Socket Mode`.

---

## Step 10 – Check the Integrations page

Open <http://localhost:5173/integrations>.

The Slack card should show:

- Status **Connected** and your **workspace name**
- All four checks ticked: *Integration enabled*, *Bot and app tokens set*, *Credentials verified
  by Slack*, *Worker running*

Under **Channels**:

- If you set `SLACK_CHANNEL_IDS`, `#noc-test` is already **Monitored**.
- Otherwise click **Monitor** next to `#noc-test` (or type the channel ID and click **Monitor
  channel**).

Only monitored channels are read. Everything else is ignored.

---

## Step 11 – Run the demo conversation

In Slack, in `#noc-test`:

1. **Engineer A** posts a new message:
   > The network connection keeps dropping at Site 42.
2. **Engineer B** hovers over that message → **Reply in thread**:
   > Did you try restarting the affected service rather than rebooting the whole router?
3. **Engineer A** replies **in the same thread**:
   > Yes, restarting that service fixed it.

Replies must be **in the thread**. Messages posted directly in the channel are treated as
separate conversations.

---

## Step 12 – Watch Elisa Echo pick it up

About 15 seconds after the last message (Elisa Echo waits for the conversation to settle):

1. **Integrations → Connector activity:** "New message from …", then the analysis result and
   "Embedded for semantic search".
2. **Live Discovery:** the conversation appears labelled **Slack #noc-test**, with the extracted
   fix marked *Confirmed in conversation* and *Not an approved procedure*.
3. **Knowledge Base:** the new item, with the three Slack messages as evidence and links back to
   Slack.
4. **Search:** try different words, e.g. *customers lose connectivity, rebooting didn't help*.
   Open the result.
5. Click **Build a troubleshooting guide**.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| Integrations says **Not set up** | `SLACK_ENABLED=true` is missing, or the containers were not recreated (step 9). |
| **Not configured** | One of the tokens is missing in `backend/.env`. |
| **Error: Slack rejected the bot token (invalid_auth)** | Wrong or old `xoxb-` token. Copy it again from **OAuth & Permissions**, then repeat step 9. |
| **Worker not running** | Run `docker compose up -d slack-worker` and check `docker compose logs slack-worker`. |
| Connected, but no messages arrive | (1) Event `message.channels` not saved (step 5), (2) app not reinstalled after changes, (3) app not invited to the channel, (4) channel not **Monitored**. |
| "App not in channel" on Integrations | Run `/invite @YourAppName` in that channel. |
| Messages arrive but no knowledge | Make sure the replies are **in a thread**; plain chatter is (correctly) ignored. Check the activity log for Gemini errors such as quota limits. |
| Author shows as an ID like `U0123…` | The `users:read` scope is missing. Add it and reinstall. |

---

## Turning it off

- Stop monitoring a channel: **Integrations → Stop monitoring**.
- Disconnect completely: set `SLACK_ENABLED=false` in `backend/.env` and run step 9 again.
- Revoke access: in the Slack app settings → **Install App** → **Revoke** (or delete the app).
  Already discovered knowledge stays in Elisa Echo.
