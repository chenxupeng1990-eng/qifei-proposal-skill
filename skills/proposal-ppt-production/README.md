# proposal-ppt-production

Production subskill for turning confirmed proposal page contracts into reviewable 16:9 pages through either HTML plus PNG or direct PNG plus Cowart, then assembling the final deck after approval.

The active project's `DESIGN.md` controls brand styling. This package supplies production routing, visual-carrier selection, QA, and final-assembly rules; it does not contain client material or authorize content changes. Its deterministic utilities handle mechanical work only: validation, asset staging, measured layout capture, rendering, comparison, and packaging. They never autofill proposal judgment or infer approval.

## Windows compatibility

The rules-only package has no platform-specific runtime. Its validator requires Node.js 18+ and accepts quoted Windows paths. When used through the company proposal runtime, install Node.js 18+, Python 3.9+, and Edge or Chrome. Use `py -3` or `python` in place of Unix-only `python3` commands. PowerShell is recommended for paths containing spaces or CJK characters.
