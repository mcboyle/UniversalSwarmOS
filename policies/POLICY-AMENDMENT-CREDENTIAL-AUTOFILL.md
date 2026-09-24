# Policy Amendment Proposal: Authorized In-Browser Credential Autofill

**Status**: **RATIFIED BY OPERATOR** (2026-09-24T20:36:24Z)  
**Subject**: Allowing Virtual Browser Oracle to trigger password manager autofill on authorized AI sites.

---

## 1. Context & Technical Assessment
The operator requested permission to allow the agent to utilize the installed password manager (Proton Pass / Chrome Credential Manager) on nodes `10.0.70.181` and `10.0.10.137` to prevent manual re-login friction when AI oracle sessions expire.

### Security Invariants & Boundaries
- **Strict Prohibition (Unchangeable)**: The agent will **never** read, log, dump, export, or exfiltrate plaintext passwords or master vault keys.
- **Permissible Scope**: The agent may trigger in-browser autofill UI elements and click submission buttons strictly on authorized AI oracle domains (`claude.ai`, `chatgpt.com`, `gemini.google.com`).

---

## 2. Policy Options & Consequences

### Option 1: In-Browser Autofill Interaction (Recommended)
- **Mechanism**: If an oracle session drops to a login page, the agent triggers the password manager's autofill button/overlay in the DOM and clicks "Sign In".
- **Pre-requisite**: The password manager extension remains unlocked on the desktop session.
- **Safety**: Passwords remain inside the browser memory/extension sandbox; the agent never extracts or logs credentials.
- **Consequence**: Automatic recovery from session expiration without human intervention.

### Option 2: Chrome Native Password Manager Storage
- **Mechanism**: Save the AI account credentials directly into Chrome's native credential store (`chrome://password-manager`). Chrome natively populates the form upon page load, and the agent clicks "Submit".
- **Pre-requisite**: Credentials saved once in Chrome.
- **Safety**: Natively bound to the local Windows user profile (DPAPI encrypted).
- **Consequence**: Bypasses extension UI race conditions, highly reliable headless recovery.

### Option 3: Maintain Strict Human-Only Authentication (Current Baseline)
- **Mechanism**: Agent halts on login screens and emits a re-authentication prompt for the operator.
- **Safety**: Zero interaction with credential fields.
- **Consequence**: Requires operator intervention whenever a cookie expires.
