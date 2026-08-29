# Setup: live Mission Telemetry + Contribution Snake

Complete this checklist in the profile repository at
`github.com/thotashashank302/thotashashank302`.

## 1. Create the telemetry token

- [ ] Open **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**.
- [ ] Select **Generate new token (classic)**.
- [ ] Enable only the `read:user` scope. Public data is sufficient; `repo` is not required.
- [ ] Copy the token when GitHub shows it. Codex cannot create or recover this token for you.
- [ ] Open the profile repository → **Settings → Secrets and variables → Actions → New repository secret**.
- [ ] Set the secret name to `TELEMETRY_TOKEN`.
- [ ] Paste the copied token as the secret value and save it.

The default `GITHUB_TOKEN` can be unable to read the GraphQL
`contributionsCollection` field, so the telemetry workflow uses this dedicated
read-only token.

## 2. Enable workflow write permissions

- [ ] Open the profile repository → **Settings → Actions → General**.
- [ ] Under **Workflow permissions**, select **Read and write permissions**.
- [ ] Save the setting.

Both workflows commit generated files back to the repository, so write access
is required.

## 3. Populate the assets once

- [ ] Open the repository **Actions** tab.
- [ ] Select **Update Mission Telemetry** → **Run workflow** → **Run workflow**.
- [ ] Select **Generate Contribution Snake** → **Run workflow** → **Run workflow**.
- [ ] Confirm that the runs succeed and that the repository contains:
  - `assets/telemetry.svg`
  - `assets/snake-dark.svg`
  - `assets/snake-light.svg`

## Refresh schedule

- Mission Telemetry refreshes daily at `03:17 UTC`.
- Contribution Snake refreshes every six hours.
- Both workflows can also be run manually with `workflow_dispatch`.

The workflow colors use the same navy, electric-blue, and violet palette as the
banner and README badges.
