# Credential Detection Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the false-positive/false-negative bugs in `src/features/string_patterns.py`'s credential detection (`count_hardcoded_passwords`, `count_credential_pairs`) without changing their public signatures, the `scan_strings()` feature schema, or `scoring.py`.

**Architecture:** Split each public function internally into "extract candidate" + "reject/accept" steps (classify-before-count), all in pure regex/stdlib Python — no LLM, no new public API, no new dependencies. Rejection filters (placeholder/variable/template/null/metadata-key) run before any positive match is counted.

**Tech Stack:** Python 3.9+, `re` (stdlib only), pytest (existing test style: plain functions + `pytest.mark.parametrize`, no fixture files).

**Spec:** `docs/superpowers/specs/2026-09-12-credential-detection-accuracy-design.md`

## Global Constraints

- No new runtime dependencies — `src/features/string_patterns.py` stays stdlib-only (`re` only).
- Public function signatures unchanged: `count_hardcoded_passwords(strings: list[str]) -> int`, `count_credential_pairs(strings: list[str]) -> int`.
- `scan_strings()` return keys unchanged — no new feature columns, no changes to `src/scoring.py` or `src/feature_extraction.py`.
- Line length 88 (ruff/black config in `pyproject.toml`), target Python 3.9 (`from __future__ import annotations` already present — keep using modern generic hints like `frozenset[str]`).
- Follow existing test style in `tests/test_string_patterns.py`: plain `def test_x() -> None:` functions grouped under `# ---` section comments, plus `pytest.mark.parametrize` for the final regression sweep (Task 5) — no new JSONL fixture files.
- Every task ends with `pytest tests/test_string_patterns.py -v` passing and a commit.

---

## Task 1: Rebuild key=value credential matching — reject non-concrete values, recognize compound/aliased keys

This is the fix for the false positive you found (`password=%s`-style matches) plus the aliasing false negatives from the report (`admin_password=`, `adminPassword=`, `ftp_pass=`, `wpa_psk=`).

**Files:**
- Modify: `src/features/string_patterns.py:15-46` (the `_PASSWORD_KV_RE` regex and `_DEFAULT_PASSWORDS` block) and `:143-160` (`count_hardcoded_passwords`)
- Test: `tests/test_string_patterns.py:16-51` (the `count_hardcoded_passwords` section)

**Interfaces:**
- Produces: `_is_credential_key(key: str) -> bool`, `_is_rejected_value(value: str) -> bool`, `_has_plaintext_credential(s: str) -> bool` — all used by Task 3 (pairs reuse `_is_rejected_value`) and Task 5 (regression sweep).
- Consumes: nothing from other tasks (first task).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_string_patterns.py`, right after `test_passwords_kv_case_insensitive` (do not remove any existing test yet):

```python
def test_passwords_rejects_format_specifier() -> None:
    assert count_hardcoded_passwords(["password=%s"]) == 0


def test_passwords_rejects_format_specifier_precision() -> None:
    assert count_hardcoded_passwords(["password=%.*s"]) == 0


def test_passwords_rejects_variable_reference() -> None:
    assert count_hardcoded_passwords(["password=${PASSWORD}"]) == 0


def test_passwords_rejects_variable_reference_positional() -> None:
    assert count_hardcoded_passwords(["password=$1"]) == 0


def test_passwords_rejects_template() -> None:
    assert count_hardcoded_passwords(["password={{password}}"]) == 0


def test_passwords_rejects_angle_template() -> None:
    assert count_hardcoded_passwords(["password=<password>"]) == 0


def test_passwords_rejects_null_literal() -> None:
    assert count_hardcoded_passwords(["password=NULL"]) == 0


def test_passwords_rejects_none_literal() -> None:
    assert count_hardcoded_passwords(["password=None"]) == 0


def test_passwords_rejects_parenthesized_null() -> None:
    assert count_hardcoded_passwords(["password=(null)"]) == 0


def test_passwords_rejects_metadata_key_length() -> None:
    assert count_hardcoded_passwords(["password_length=8"]) == 0


def test_passwords_rejects_metadata_key_hash() -> None:
    hash_val = "5f4dcc3b5aa765d61d8327deb882cf99"
    assert count_hardcoded_passwords([f"password_hash={hash_val}"]) == 0


def test_passwords_detects_compound_key_snake_case() -> None:
    assert count_hardcoded_passwords(["admin_password=admin123"]) == 1


def test_passwords_detects_compound_key_camel_case() -> None:
    assert count_hardcoded_passwords(["adminPassword=admin123"]) == 1


def test_passwords_detects_ftp_pass_alias() -> None:
    assert count_hardcoded_passwords(["ftp_pass=admin123"]) == 1


def test_passwords_detects_wpa_psk_alias() -> None:
    assert count_hardcoded_passwords(["wpa_psk=12345678"]) == 1


def test_passwords_detects_wl0_wpa_psk_alias() -> None:
    assert count_hardcoded_passwords(["wl0_wpa_psk=12345678"]) == 1


def test_passwords_query_string_after_rejected_key() -> None:
    # a rejected key=value earlier in the same (space-free) string must not
    # swallow a real credential later in the string
    assert count_hardcoded_passwords(["http://x/?mode=auto&password=admin"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_string_patterns.py -k "rejects_format_specifier or rejects_variable_reference or rejects_template or rejects_angle_template or rejects_null or rejects_none or rejects_parenthesized or rejects_metadata or detects_compound or detects_ftp_pass or detects_wpa_psk or detects_wl0 or query_string_after_rejected" -v`
Expected: several FAIL (format specifiers, variables, templates and nulls still counted as 1; compound/aliased keys still counted as 0)

- [ ] **Step 3: Replace the password-matching implementation**

In `src/features/string_patterns.py`, replace the entire "Password patterns" section (lines 11-46, from the section header comment through the closing `)` of `_DEFAULT_PASSWORDS`) with:

```python
# ---------------------------------------------------------------------------
# Password patterns
# ---------------------------------------------------------------------------

# Generic identifier=value / identifier:value scanner. The value stops at
# whitespace, "&" and ";" so that a rejected match earlier in a delimiter-free
# string (e.g. a URL query string) never swallows a real credential later in
# the same string. Whether a given key/value pair is actually a credential is
# decided afterwards by _is_credential_key() and _is_rejected_value().
_PASSWORD_KV_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]{0,40})\s*[=:]\s*([^\s&;]+)")

_CREDENTIAL_KEY_TOKENS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "pass",
        "secret",
        "credential",
        "passphrase",
        "pswd",
        "psw",
        "userpass",
        "loginpass",
        "psk",
    }
)

# A key token from this set means the match describes *metadata about* a
# credential (its length, hash, rotation policy...) rather than the
# credential itself — e.g. password_length=8, password_hash=<digest>.
_METADATA_KEY_TOKENS: frozenset[str] = frozenset(
    {"length", "len", "size", "hash", "algorithm", "algo", "policy", "timeout"}
)

_NULL_LITERALS: frozenset[str] = frozenset(
    {"null", "none", "nil", "undefined", "(null)"}
)

_VARIABLE_REF_RE = re.compile(r"^\$\{?\w+\}?$")
_TEMPLATE_RE = re.compile(r"^\{\{?\w+\}?\}$|^<\w+>$")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# TODO: Review passwords list and add more common default passwords if necessary
_DEFAULT_PASSWORDS: frozenset[str] = frozenset(
    {
        "admin",
        "password",
        "1234",
        "12345",
        "123456",
        "admin123",
        "root",
        "toor",
        "pass",
        "test",
        "1234567890",
        "guest",
        "default",
        "support",
        "supervisor",
        "service",
        "system",
        "ubnt",
        "huawei",
        "zte521",
        "telnet",
        "enable",
    }
)

_AUTH_CONTEXT_TRIGGERS: frozenset[str] = frozenset(
    {
        "login",
        "user",
        "username",
        "account",
        "credential",
        "auth",
        "senha",
        "password",
        "passwd",
        "pwd",
        "default",
    }
)
```

Then add these helpers right before `count_hardcoded_passwords` (after the `_parse_version` helper, before the "Public functions" section):

```python
def _key_tokens(key: str) -> list[str]:
    """Split a key into lowercase tokens across snake_case/kebab-case/camelCase.

    Examples::

        _key_tokens("admin_password") -> ["admin", "password"]
        _key_tokens("adminPassword") -> ["admin", "password"]
        _key_tokens("wl0_wpa_psk") -> ["wl0", "wpa", "psk"]
    """
    spaced = _CAMEL_BOUNDARY_RE.sub("_", key)
    return [t.lower() for t in re.split(r"[_-]", spaced) if t]


def _is_credential_key(key: str) -> bool:
    """Return True if *key* denotes a credential value, not metadata about one."""
    tokens = set(_key_tokens(key))
    if tokens & _METADATA_KEY_TOKENS:
        return False
    return bool(tokens & _CREDENTIAL_KEY_TOKENS)


def _is_rejected_value(value: str) -> bool:
    """Return True if *value* is a placeholder, variable ref, template or null.

    These never represent a concrete, hardcoded credential.
    """
    if value.startswith("%"):
        return True
    if _VARIABLE_REF_RE.match(value):
        return True
    if _TEMPLATE_RE.match(value):
        return True
    if value.strip("()").lower() in _NULL_LITERALS:
        return True
    return False


def _has_plaintext_credential(s: str) -> bool:
    """Return True if *s* has a key=value pair with a concrete credential."""
    for m in _PASSWORD_KV_RE.finditer(s):
        key, value = m.group(1), m.group(2)
        if not _is_credential_key(key):
            continue
        if _is_rejected_value(value):
            continue
        return True
    return False
```

Finally, replace the body of `count_hardcoded_passwords` (keep its existing docstring, just update it and the body):

```python
def count_hardcoded_passwords(strings: list[str]) -> int:
    """Count strings that contain hardcoded credentials.

    Counts key=value/key:value pairs with a concrete literal — rejecting
    format specifiers, variable references, templates, null literals and
    metadata keys (``password_length``, ``password_hash``) — plus bare
    occurrences of well-known default passwords (see
    ``_has_default_password_token``, added in Task 2).
    """
    count = 0
    for s in strings:
        if _has_plaintext_credential(s):
            count += 1
            continue
        tokens = s.split()
        if any(t.lower() in _DEFAULT_PASSWORDS for t in tokens):
            count += 1
    return count
```

(The bare-token branch keeps its old, context-free behavior for now — Task 2 tightens it. This keeps Task 1 focused solely on the key=value path.)

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_string_patterns.py -v`
Expected: all PASS, including every test added in Step 1 and every pre-existing test in the file (`test_passwords_kv_match`, `test_passwords_kv_colon`, `test_passwords_kv_case_insensitive`, `test_passwords_default_token`, `test_passwords_default_token_root`, `test_passwords_no_match`, `test_passwords_multiple_strings` all still pass unchanged — verify this explicitly, don't just trust the diff)

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/features/string_patterns.py tests/test_string_patterns.py`
Run: `mypy src/features/string_patterns.py`
Expected: no errors. Fix any line-length (88 cols) or typing issues before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/features/string_patterns.py tests/test_string_patterns.py
git commit -m "fix: reject non-concrete values and recognize compound credential keys

Claude-Session: https://claude.ai/code/session_01K7SMcapXh9XCnYgzC7QSjN"
```

---

## Task 2: Require authentication context for bare default-password token matches

**Behavior change:** today `count_hardcoded_passwords(["admin"])` returns `1` for the bare word "admin" with zero surrounding context — a major false-positive source in ordinary firmware text (`"self test"`, `"system ready"`). After this task, a bare token from `_DEFAULT_PASSWORDS` only counts when the same string also contains an authentication-context cue.

**Files:**
- Modify: `src/features/string_patterns.py` (`count_hardcoded_passwords`, function body only — the `_AUTH_CONTEXT_TRIGGERS` constant already exists from Task 1)
- Test: `tests/test_string_patterns.py` (update `test_passwords_default_token` and `test_passwords_default_token_root`; add two new tests)

**Interfaces:**
- Produces: `_has_default_password_token(s: str) -> bool` — used by Task 5's regression sweep.
- Consumes: `_AUTH_CONTEXT_TRIGGERS` (from Task 1).

- [ ] **Step 1: Update the existing tests to reflect the intended (fixed) behavior**

In `tests/test_string_patterns.py`, replace:

```python
def test_passwords_default_token() -> None:
    assert count_hardcoded_passwords(["admin"]) == 1


def test_passwords_default_token_root() -> None:
    assert count_hardcoded_passwords(["root"]) == 1
```

with:

```python
def test_passwords_default_token_without_context_not_flagged() -> None:
    # bare "admin" with zero surrounding context is too weak a signal on its
    # own (it's the false-positive source found in the first generated
    # sample) — no longer counted unless auth context is present nearby.
    assert count_hardcoded_passwords(["admin"]) == 0


def test_passwords_default_token_root_without_context_not_flagged() -> None:
    assert count_hardcoded_passwords(["root"]) == 0


def test_passwords_default_token_with_context() -> None:
    assert count_hardcoded_passwords(["default login: admin"]) == 1


def test_passwords_default_token_root_with_context() -> None:
    assert count_hardcoded_passwords(["login as root"]) == 1


def test_passwords_default_token_avoids_substring_trigger_match() -> None:
    # "auth" must not match as a substring of "authentication" — this exact
    # string is a required hard negative in the technical report (§9.3):
    # "password" is a default-password value, but this is a log message,
    # not a credential.
    assert count_hardcoded_passwords(["Password authentication failed"]) == 0
```

- [ ] **Step 2: Run tests to verify the new/changed ones fail**

Run: `pytest tests/test_string_patterns.py -k "default_token" -v`
Expected: three FAIL — `test_passwords_default_token_without_context_not_flagged`, `test_passwords_default_token_root_without_context_not_flagged` (current code returns 1 for a bare token with zero context) and `test_passwords_default_token_avoids_substring_trigger_match` (current code has no context filter at all, so the bare word "Password" in "Password authentication failed" is counted as 1, not the expected 0). The two `_with_context` tests already PASS, but only incidentally — the pre-Task-2 code counts "admin"/"root" regardless of context, so it happens to agree with the expected value of 1. Step 3 makes every one of these pass for the *right* reason.

- [ ] **Step 3: Implement the context-gated token check**

In `src/features/string_patterns.py`, add this helper right after `_has_plaintext_credential`:

```python
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _has_default_password_token(s: str) -> bool:
    """Return True if *s* has a weak password token with auth context nearby.

    A bare occurrence of a common word like "test" or "admin" is too weak a
    signal alone (ordinary firmware text is full of them — "self test",
    "system ready"). Require an authentication-context cue elsewhere in the
    same string before counting it as a credential.

    Matching is whole-word, not substring: a naive substring check would
    match the trigger "auth" inside "authentication", wrongly flagging the
    hard negative "Password authentication failed" (report §9.3) as a
    credential just because "password" is also a default-password value.
    """
    words = [w.lower() for w in _WORD_RE.findall(s)]
    word_set = set(words)
    for t_lower in words:
        if t_lower not in _DEFAULT_PASSWORDS:
            continue
        if word_set & (_AUTH_CONTEXT_TRIGGERS - {t_lower}):
            return True
    return False
```

Then update `count_hardcoded_passwords` to use it instead of the inline token check:

```python
def count_hardcoded_passwords(strings: list[str]) -> int:
    """Count strings that contain hardcoded credentials.

    Counts key=value/key:value pairs with a concrete literal — rejecting
    format specifiers, variable references, templates, null literals and
    metadata keys (``password_length``, ``password_hash``) — plus bare
    occurrences of well-known default passwords that appear alongside an
    authentication-context cue (see ``_has_default_password_token``).
    """
    count = 0
    for s in strings:
        if _has_plaintext_credential(s) or _has_default_password_token(s):
            count += 1
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_string_patterns.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/features/string_patterns.py tests/test_string_patterns.py`
Run: `mypy src/features/string_patterns.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/features/string_patterns.py tests/test_string_patterns.py
git commit -m "fix: require auth context for bare default-password token matches

Claude-Session: https://claude.ai/code/session_01K7SMcapXh9XCnYgzC7QSjN"
```

---

## Task 3: Relax credential-pair matching to require only a recognized username

**Behavior change:** today `count_credential_pairs` requires *both* sides of a `user:pass` pair to be in the weak-value list, so `admin:S3cur3Pass9` (real credential, strong password) is missed. After this task, only the username side must be recognized — the password side just needs to not be a placeholder/null (reusing Task 1's `_is_rejected_value`).

**Files:**
- Modify: `src/features/string_patterns.py` (`_CRED_PAIR_WEAK` rename + `count_credential_pairs`)
- Test: `tests/test_string_patterns.py` (`count_credential_pairs` section)

**Interfaces:**
- Consumes: `_is_rejected_value(value: str) -> bool` (Task 1).
- Produces: `_has_weak_username_pair(s: str) -> bool`, `_CRED_PAIR_USERNAMES` — used by Task 4.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_string_patterns.py`, after `test_cred_pairs_long_hash_ignored`:

```python
def test_cred_pairs_strong_password_with_known_username() -> None:
    # username is recognized; password is strong/unlisted — still a real pair
    assert count_credential_pairs(["admin:S3cur3Pass9"]) == 1


def test_cred_pairs_rejects_placeholder_password() -> None:
    assert count_credential_pairs(["admin:%s"]) == 0
```

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `pytest tests/test_string_patterns.py -k "strong_password_with_known_username or rejects_placeholder_password" -v`
Expected: `test_cred_pairs_strong_password_with_known_username` FAILS (current code requires both sides weak; `S3cur3Pass9` isn't in `_CRED_PAIR_WEAK`); `test_cred_pairs_rejects_placeholder_password` — check: `%s` isn't alnum so the current `_CRED_PAIR_RE` (`[A-Za-z0-9]{1,20}`) already fails to match `admin:%s` at all, so this one already PASSES. That's fine — it becomes a permanent regression guard for Step 3's rewrite.

- [ ] **Step 3: Rename the weak set and rewrite `count_credential_pairs`**

In `src/features/string_patterns.py`, find the "Credential pair patterns" section and rename `_CRED_PAIR_WEAK` to `_CRED_PAIR_USERNAMES`, updating its docstring/comment:

```python
# ---------------------------------------------------------------------------
# Credential pair patterns (user:pass where the username is recognizable)
# ---------------------------------------------------------------------------

_CRED_PAIR_RE = re.compile(r"\b([A-Za-z0-9]{1,20}):([A-Za-z0-9]{1,20})\b")
_CRED_PAIR_USERNAMES: frozenset[str] = frozenset(
    {
        "admin",
        "root",
        "guest",
        "test",
        "default",
        "user",
        "support",
        "supervisor",
        "service",
        "system",
        "ubnt",
        "huawei",
        "zte521",
        "password",
        "1234",
        "12345",
        "123456",
        "admin123",
        "toor",
        "pass",
        "enable",
        "telnet",
    }
)
```

Add this helper right after the constants:

```python
def _has_weak_username_pair(s: str) -> bool:
    """Return True if *s* has a user:pass pair with a recognizable username.

    The password side is not required to be weak — a recognizable username
    (``admin``, ``root``...) paired with *any* concrete secret is itself the
    signal; only placeholders/nulls on the password side are rejected.
    """
    for m in _CRED_PAIR_RE.finditer(s):
        username, secret = m.group(1), m.group(2)
        if username.lower() not in _CRED_PAIR_USERNAMES:
            continue
        if _is_rejected_value(secret):
            continue
        return True
    return False
```

Replace `count_credential_pairs`'s body (keep updating its docstring):

```python
def count_credential_pairs(strings: list[str]) -> int:
    """Count strings containing a user:pass credential pair.

    Matches colon-separated pairs where the username is a known
    default/weak value (``admin:S3cur3Pass9``) — the password side only
    needs to be a concrete, non-placeholder value. Counts per string, not
    per match — a string with multiple pairs is counted once.
    """
    count = 0
    for s in strings:
        if _has_weak_username_pair(s):
            count += 1
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_string_patterns.py -v`
Expected: all PASS, including all pre-existing `test_cred_pairs_*` tests (`admin_admin`, `root_1234`, `non_weak_ignored`, `long_hash_ignored`, `multiple_strings`, `multiple_in_one_string_counts_once`) — confirm none regressed.

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/features/string_patterns.py tests/test_string_patterns.py`
Run: `mypy src/features/string_patterns.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/features/string_patterns.py tests/test_string_patterns.py
git commit -m "fix: only require recognizable username for credential pairs

Claude-Session: https://claude.ai/code/session_01K7SMcapXh9XCnYgzC7QSjN"
```

---

## Task 4: Add URL userinfo credential-pair detection

Firmware often embeds default API/service credentials directly in a URL (`http://admin:S3cr3t@host/`). This adds a dedicated extraction for that family, feeding the same `count_credential_pairs`.

**Files:**
- Modify: `src/features/string_patterns.py` (`count_credential_pairs`)
- Test: `tests/test_string_patterns.py` (`count_credential_pairs` section)

**Interfaces:**
- Consumes: `_is_rejected_value` (Task 1).
- Produces: `_has_url_userinfo_pair(s: str) -> bool` — used by Task 5's regression sweep.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_string_patterns.py`, after `test_cred_pairs_rejects_placeholder_password`:

```python
def test_cred_pairs_url_userinfo() -> None:
    assert count_credential_pairs(["https://apiuser:Str0ngP4ss@iot.example.com/"]) == 1


def test_cred_pairs_url_userinfo_rejects_placeholder() -> None:
    assert count_credential_pairs(["https://user:%s@host/"]) == 0


def test_cred_pairs_url_userinfo_http() -> None:
    assert count_credential_pairs(["http://admin:admin@192.168.1.1/"]) == 1
```

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `pytest tests/test_string_patterns.py -k "url_userinfo" -v`
Expected: `test_cred_pairs_url_userinfo` FAILS (no URL-family extraction exists yet — `apiuser` isn't a recognized username so `_has_weak_username_pair` won't catch it). The other two may already pass incidentally via `_has_weak_username_pair` (both usernames happen to be `%s`-rejected or `admin`-recognized) — that's fine, they become permanent regression guards for Step 3.

- [ ] **Step 3: Add the URL userinfo extractor**

In `src/features/string_patterns.py`, add right after `_CRED_PAIR_USERNAMES`:

```python
_URL_USERINFO_RE = re.compile(r"https?://([^\s:@/]{1,32}):([^\s@/]{1,64})@")


def _has_url_userinfo_pair(s: str) -> bool:
    """Return True if *s* has a user:pass pair embedded in a URL's userinfo.

    The URL's own protocol delimiter (``scheme://user:pass@``) is a strong
    enough structural signal on its own — the username does not need to be
    on the recognized-username list, unlike ``_has_weak_username_pair``.
    """
    for m in _URL_USERINFO_RE.finditer(s):
        secret = m.group(2)
        if _is_rejected_value(secret):
            continue
        return True
    return False
```

Update `count_credential_pairs`:

```python
def count_credential_pairs(strings: list[str]) -> int:
    """Count strings containing a user:pass credential pair.

    Matches colon-separated pairs where the username is a known
    default/weak value (``admin:S3cur3Pass9``), and userinfo credentials
    embedded in URLs (``https://apiuser:Str0ngP4ss@host/``) — the URL's
    protocol delimiter is itself a strong structural signal, so the
    username is not required to be on the weak list there. Counts per
    string, not per match — a string with multiple pairs is counted once.
    """
    count = 0
    for s in strings:
        if _has_weak_username_pair(s) or _has_url_userinfo_pair(s):
            count += 1
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_string_patterns.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/features/string_patterns.py tests/test_string_patterns.py`
Run: `mypy src/features/string_patterns.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/features/string_patterns.py tests/test_string_patterns.py
git commit -m "feat: detect credential pairs embedded in URL userinfo

Claude-Session: https://claude.ai/code/session_01K7SMcapXh9XCnYgzC7QSjN"
```

---

## Task 5: Regression sweep from the technical report + final verification

Consolidates the report's hard-negative (§9.3) and boundary-case (§6.2) examples into one parametrized regression block, so this exact bug class can't silently reappear. Also the final full-suite/lint/type gate for the branch.

**Files:**
- Modify: `tests/test_string_patterns.py` (new section at the end of the file)

**Interfaces:**
- Consumes: `count_hardcoded_passwords`, `count_credential_pairs` (public API, unchanged signatures).

- [ ] **Step 1: Add the parametrized regression block**

Add to the end of `tests/test_string_patterns.py`:

```python
# ---------------------------------------------------------------------------
# Regression sweep — hard negatives and boundary cases from
# docs/Relatorio_Tecnico_LLM_Deteccao_Credenciais_Firmware.pdf (§6.2, §9.3)
# ---------------------------------------------------------------------------

_REPORT_PASSWORD_CASES = [
    # (text, expected count_hardcoded_passwords)
    ("password=%s", 0),
    ("password=${PASSWORD}", 0),
    ("password=NULL", 0),
    ("password_length=8", 0),
    ("Password authentication failed", 0),
    ("setPassword", 0),
    ("/etc/passwd", 0),
    ("passwd.c", 0),
    ("confirm password", 0),
    ("wpa_psk=12345678", 1),
    ("ftp_pass=admin123", 1),
    ("adminPassword=admin123", 1),
]


@pytest.mark.parametrize("text,expected", _REPORT_PASSWORD_CASES)
def test_report_password_regression(text: str, expected: int) -> None:
    assert count_hardcoded_passwords([text]) == expected


_REPORT_PAIR_CASES = [
    # (text, expected count_credential_pairs)
    ("admin:admin123", 1),
    ("http://admin:admin@192.168.1.1/", 1),
]


@pytest.mark.parametrize("text,expected", _REPORT_PAIR_CASES)
def test_report_pair_regression(text: str, expected: int) -> None:
    assert count_credential_pairs([text]) == expected
```

Add `import pytest` at the top of the file (after the existing `from src.features.string_patterns import (...)` block).

- [ ] **Step 2: Run the new tests and verify they fail or pass as expected**

Run: `pytest tests/test_string_patterns.py -k "report_" -v`
Expected: all PASS immediately (Tasks 1-4 already implement every rule this sweep exercises) — this step is a verification, not a red/green cycle. If anything FAILS, that means one of Tasks 1-4 has a gap; go back and fix the relevant task's implementation before continuing (do not adjust the expected values to match broken behavior).

- [ ] **Step 3: Run the full test suite for the whole project**

Run: `pytest -v`
Expected: all PASS — this catches any unexpected interaction with `test_feature_extraction.py`, `test_scoring.py`, `test_feature_vector.py` or other consumers of `string_patterns`.

- [ ] **Step 4: Full lint and type-check gate**

Run: `ruff check src/ tests/`
Run: `mypy src/`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add tests/test_string_patterns.py
git commit -m "test: add regression sweep from credential-detection technical report

Claude-Session: https://claude.ai/code/session_01K7SMcapXh9XCnYgzC7QSjN"
```

---

## Post-implementation note (not a task — do not automate)

`scan_strings()`'s two feature values now mean something more precise, but the *dataset already extracted* under `dataset/` still holds values computed with the old, noisier logic. Before the next model training run, re-run `extract-features` over the corpus so `count_hardcoded_passwords` / `count_credential_pairs` reflect the fixed logic. This is a manual step for whoever trains next — out of scope for this branch per the design spec.
