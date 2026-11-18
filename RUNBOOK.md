# Runbook: inkindstandard.org

Prepared by In-Kind Standard · Citizen-prepared working draft · Not legal advice

How to build, check and publish this site, and how to keep it running, so that anyone given access to its accounts can carry on from this repository alone. Nothing here is a password or a recovery detail.

Known gaps: no county has adopted the model documents, no lawyer has reviewed them, and there is no organization yet.

## 1. What runs where

| Part | Where it runs | Who holds it |
|---|---|---|
| This site | GitHub Pages, from the `docs/` folder of this repository's `main` branch | The GitHub organization InKindStandard, whose owner is the founder |
| The address inkindstandard.org | Registered at Porkbun, which also keeps its DNS records | The founder's Porkbun account |
| The contact address, contact@inkindstandard.org | Google Workspace | The project's Google Workspace account |
| The permanent copies of the model documents | Zenodo, with a DOI for each part of each release | The account that deposits the project's releases |
| The page "What Florida counties can do about a large data center", at https://screen.inkindstandard.org/ | GitHub Pages, from its own repository | The same GitHub organization |

The founder keeps a sealed recovery kit, offline, for the day an account cannot be reached the usual way. Every account must use two-step sign-in.

## 2. What you need

- Python 3.10 or later. The build and `checks/check_site.py` need nothing else.
- For the look check, `checks/look_check.py`: the Python package playwright (`pip install playwright`), Google Chrome or Chromium, and the axe-core accessibility checker, installed with Node.js's `npm install axe-core` in a scratch folder. Its opening lines say how to point to the browser and to axe-core.
- Git and access to this repository.

## 3. Make a change

1. Change the source, never the published files: a page's text in `src/pages/`, the header and footer in `src/layout.html`, the style sheet and the script in `src/assets/`. Each page begins with a short heading block (its title, address, description, date, word budget and ceiling); keep it.
2. Build: `python3 build.py`. It writes `docs/` from `src/`, and an error leaves `docs/` as it was.
3. Check, in order, and fix the cause of any failure; never weaken a check to make it pass:
   - `python3 build.py --check`: the published files match the script.
   - `python3 checks/check_site.py`: the rules in section 6.
   - `python3 checks/look_check.py`, with `CHROME` and `AXE` set; before a publication, also with `SWEEP=1`, which tries every width from 320 to 720 pixels and takes a few minutes more.
4. New or changed words pass the Neutrality Test of the project's Political Neutrality Policy (section 3.13), and a second check by an AI tool, in a session that did not draft them, before they are published. Before each publication, every public file is also read for anything private: a password or a code, a personal address or telephone number, a private place or name, or a weakness in an account's security.
5. Commit the change with Git on a branch of its own and open a pull request, with a short description and the checks' results. `main` is protected (section 7): a change reaches it only through a pull request, which the founder reviews and merges; the merge publishes it, and GitHub Pages serves the new `docs/` within minutes. AI tools help build and check this site, and the founder reviews every page and decides what is published, except work the founder steps aside from because of a tie. A tie means a connection that might be, or look like, a conflict of interest. An AI tool may prepare and propose a change; it does not merge one.
6. Once it is live, open the changed pages at https://inkindstandard.org and look at them.

## 4. Add a release of the model documents

When a new release is deposited at Zenodo:

1. Put its files in `docs/files/{release}/{record}/`, unchanged, in two folders: `instruments` (Record 1) and `guide` (Record 2), as for 2026.4.
2. Save Zenodo's list of each record's files as `src/releases/{release}.zenodo.json`, in the shape of the 2026.4 file. Read it from Zenodo itself: its records interface, `https://zenodo.org/api/records/{record id}`, gives each file's name, size and MD5 checksum. Until step 3 is done, `check_site.py` stops and says why.
3. Run `python3 tools/make_release_data.py {release}` and read the result. It stops, and says why, if a file it needs is missing or a version in a file name differs from the release's change log.
4. Copy `src/pages/materials-2026.4.html` to a page for the new release. Change its heading block, breadcrumb and heading, and the release number in its text and in each link to a hosted file. Read its paragraphs against the new release's start-here file.
5. Before building, ask the founder what happens to the release it replaces: whether its page and files stay at their address, linked from the Materials page, or leave the site, Zenodo keeping them. Then make `src/releases/earlier.json`, the Materials page's words and its word budget and ceiling (`APPROVED` in `checks/check_site.py`) agree with that answer: `checks/check_site.py` fails on a page that no other page links to, and on a page over its ceiling. Set the new release page's approved ceiling in `RELEASE_CEILING` in `checks/check_site.py`.
6. In `src/pages/index.html` and `src/pages/materials.html`, change the release number in the words and in every link and placeholder that names it, and `CURRENT` in `build.py`. Build, run the checks, and read the built pages as text (`python3 tools/pages_as_text.py`) before publishing: the checks hold those pages' buttons and DOIs to the newest release, not every other mention of its number.
7. If a correction note is posted on a record at Zenodo, show it at the top of the release page, dated, beginning "Correction," and the date.

## 5. A new version of the organization's texts

Some pages show the organization's own texts, such as its funding statement, released as HTML in a dated folder with a `SHA256SUMS.txt` file and a README. The site shows them unchanged:

1. Copy the new folder's pages and checksum list, unchanged, into a folder of the same name in `src/released/nonprofit/`, beside the one in use, and check each page against the list. Leave out its README, a note to this project; `.gitignore` keeps such READMEs out of the repository too.
2. Read what changed against the texts it is made from. The site shows a version only once the founder approves it.
3. In the page's heading block, `theirs:` names the new folder's files in order. In `checks/check_site.py`, `RELEASED_PAGES` names the same files and `RELEASED_SHA` their checksums; the check fails while the two disagree.
4. Move the older folder out of `src/released/`: the check fails while a folder no page shows is there.
5. Build, run the checks, and publish as in section 3.

## 6. What the checks hold

`checks/check_site.py` states each rule where it applies it. In brief, every page:

- carries the status line, the known gaps and its date; the byline appears once, on the home page, and every other page links to it;
- keeps its own words within its word budget plus 5 percent (`ROOM`), and all its words within the ceiling set for it;
- quotes other people's words word for word, marked as theirs;
- links to the site's own pages only where they exist (links to other sites are not tried), and loads nothing from another host;
- has one main heading, a skip link, the site's one script, and no forms, frames, embedded media or tables but its ledger;
- has a contrast of at least 7 to 1 for text and 3 to 1 for controls and focus marks, in light and dark colors;
- carries the Political Neutrality Policy's words on the founder's review (section 3.19) wherever it uses a word in `AI_NAMED`.

Every hosted file must also match the checksum its release published, and the logo's mark, its two files and the browser icon theirs (`MARK_SHA`, `LOGO_FILES`, `ICON_SHA`; a new one needs the founder's approval). The script has no network, cookie, library or timer and keeps one setting, the color choice; the script is at most 30 KB, the style sheet 40 KB and a first visit 350 KB. The look check also watches what the pages do: no cookie, no request for anything but the site's own files, no stored setting but the color choice, and nothing that moves of itself. Comments in the code cite review runs and decision sheets by number; those working papers are not in this repository, and nothing here needs them. The check also holds this repository's own documents, `README.md`, `RUNBOOK.md` and `NOTICE.md`: the byline, the known gaps and a dated last line; the line on AI tools (in `NOTICE.md`, wherever it uses such a word); their word budgets; and `LICENSE`, by its checksum. It also looks for some forms of private details and secrets: in these documents, a telephone number, some setup keys and generated codes, HTML or "<" before a letter or "/", even in code, and link or footnote definitions; in every file it reads as text but the hosted release files and the released folders' READMEs, which it checks `.gitignore` keeps out, an email address other than the contact address, a GitHub token, a Google or Porkbun API key, or a private key. A form it does not know passes, so these rules do not replace the read before each publication (section 3). Its rules come from the project's policies and the founder's decisions; changing one is a change to the site (section 3).

## 7. Hosting and the address

**GitHub Pages.** In the repository's settings, under Pages: source "Deploy from a branch", branch `main`, folder `/docs`; custom domain inkindstandard.org; "Enforce HTTPS" on. Saving the custom domain makes GitHub commit a file named `CNAME` that holds the address: leave it where GitHub puts it, and after each publication check that the Pages settings still show the custom domain. The empty `docs/.nojekyll` stops GitHub from processing the files. The domain is verified for the organization by a TXT record that stays in DNS. Issues, Discussions, Wiki and Projects are off: reports come by email.

**Protecting `main`.** Under Branches, a rule for `main` (GitHub's page "Managing a branch protection rule"): "Require a pull request before merging"; "Do not allow bypassing the above settings", so that the rule holds for administrators too; and "Restrict who can push to matching branches", to the founder alone. "Allow force pushes" and "Allow deletions" stay off. Leave "Require approvals" off: a pull request's author cannot approve it (GitHub's page "Approving a pull request with required reviews"), so with no bypass it would stop the founder merging his own pull requests. Save the custom domain before adding the rule: saving it makes GitHub commit the `CNAME` file directly to the branch (its page "Managing a custom domain for your GitHub Pages site"; the three pages read 13 November 2026). Two tests were set for when the repository was created. First, an AI tool's connection can merge: on 14 November 2026 it was found to act as the founder's own GitHub account, with his role, so the rule cannot tell it from him. The founder kept it so and left a separate account for it as a later choice; that no AI tool merges rests on the instruction in section 3. Second, not yet tried: the custom domain was saved at the first publication, before the rule existed. The next time it must be saved, try it with the rule on; if GitHub refuses, lift the rule for that one change and restore it at once.

**DNS at Porkbun.** For the site: four A records for the bare address, to 185.199.108.153, 185.199.109.153, 185.199.110.153 and 185.199.111.153; four AAAA records, to 2606:50c0:8000::153, 2606:50c0:8001::153, 2606:50c0:8002::153 and 2606:50c0:8003::153 (GitHub's published addresses); and a CNAME record for `www` to `inkindstandard.github.io`. The other records are not the site's: `screen`, the mail records (MX, SPF, DKIM and DMARC) and the verification records. Change only the site's.

**After a DNS change.** It can take up to 24 hours to spread. HTTPS can take up to an hour after that, and "Enforce HTTPS" may not be offered for up to 24 hours. If it is still not offered once DNS has settled, remove the custom domain in the Pages settings and add it again. Once the rule for `main` exists, adding it makes GitHub commit the `CNAME` file again: the second test under "Protecting `main`" says how.

**Character set.** The hosted documents are UTF-8 text with typographic quotation marks. A browser shows them correctly only when the host states the character set, as GitHub Pages does. After any move to another host, open one `.txt` and one `.md` file and look for garbled quotation marks. A plain test server such as `python3 -m http.server` states none, so the files look garbled there; that is the server, not the files.

## 8. Renewals and costs

- The address: registered at Porkbun, paid through 2 November 2028, and set to renew automatically.
- Hosting: no charge; GitHub Pages is free for a public repository.
- Email: Google Workspace, billed monthly.

Each year, check the renewal date and the payment details on file.

## 9. When something breaks

| What you see | What to do |
|---|---|
| The site does not load | Check GitHub's status page, then the DNS records in section 7. The site is plain files: while GitHub is down, `docs/` can be served from any static host, with the address pointed there. |
| A browser warns about the certificate | See "After a DNS change" in section 7. |
| A check fails | Read its message, which names the page and the rule, and fix the cause. |
| A hosted file shows garbled quotation marks | See "Character set" in section 7. |
| An account cannot be reached | Use the service's own recovery first, then the sealed recovery kit. |
| Mail to the contact address stops arriving | Check the mail records at Porkbun and the account at Google Workspace. |

## 10. Handing over

- Give each account a second administrator where the service allows one.
- When the organization or a fiscal sponsor can hold them, the address, the GitHub organization, the email account and the account that deposits the releases at Zenodo move to its name.
- Keep this runbook true: a change to an account, a setting or a step is written here in the same pull request.

Updated 18 November 2026.
