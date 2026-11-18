# inkindstandard.org

Prepared by Timothy Smith · Citizen-prepared working draft · Not legal advice

This repository holds the source of the website of In-Kind Standard, https://inkindstandard.org. In the project's own words: "In-Kind Standard is a citizen-prepared, nonpartisan project, planned to run as a charitable nonprofit. It writes free model documents that Florida counties may use when a large data center seeks to locate there, and keeps a public record of what Florida counties and cities have done and what communities could receive."

Known gaps: no county has adopted the model documents, no lawyer has reviewed them, and there is no organization yet.

## What is here

| Folder or file | What it holds |
|---|---|
| `docs/` | The published site: plain HTML and CSS, a script, the fonts, and the files of each release the site hosts. GitHub Pages publishes this folder. |
| `src/` | Each page's text, the one header and footer, the style sheet, the script, the logo, the fonts, and the lists the release pages are made from. |
| `build.py` | Joins the pages to the header and footer and writes `docs/`. It needs Python 3.10 or later and nothing else. |
| `checks/` | The checks every change must pass before it is published. |
| `tools/` | Two helpers: one makes a release's list of documents, one writes the pages as plain text for anyone reviewing the words. |
| `RUNBOOK.md` | How to build, check and publish the site, and how to keep it running. |
| `NOTICE.md`, `LICENSE` | Which license covers what. |

## How the site is built and checked

The site is a small set of plain files. It works without JavaScript, which adds color buttons, reader tabs, some motion and closed disclosures on screen, and has no forms, cookies or analytics; nothing on it is loaded from another host. To build it, run `python3 build.py`. To read it locally, run `python3 build.py --local` and open `local/index.html`.

Every change passes the site's checks before it is published: `python3 build.py --check`, which confirms the published files match the script; `python3 checks/check_site.py`, for links, page structure, required words, color contrast and every hosted file's checksum; and `python3 checks/look_check.py`, which opens each page in a browser at phone and desktop widths and, given axe-core, runs that accessibility checker (`RUNBOOK.md`, section 2). New words also pass the Neutrality Test of the project's Political Neutrality Policy (section 3.13) and a second check by an AI tool, in a session that did not draft them. AI tools help build and check this site, and the founder reviews every page and decides what is published, except work the founder steps aside from because of a tie. A tie means a connection that might be, or look like, a conflict of interest.

## Report a problem

To report a mistake or an accessibility barrier, write to contact@inkindstandard.org.

## Licenses

The site's code is under CC0 1.0 (`LICENSE`). The site's own text is under CC BY 4.0. The hosted model documents and guide keep the licenses their release gives them. The name In-Kind Standard and its logo are not licensed. `NOTICE.md` says which license covers which files.

Updated 18 November 2026.
