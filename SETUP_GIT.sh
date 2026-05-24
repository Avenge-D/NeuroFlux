# Run these commands in Git Bash or any terminal where `git` is available
# (e.g. VS Code terminal, Git Bash, WSL)

cd X:/NeuroFlux

# 1. Initialize the repository
git init

# 2. Stage everything (the .gitignore will automatically exclude secrets/binaries)
git add .

# 3. Verify nothing sensitive is staged — MUST be clean
git status
# !! If you see `.env` in the list, stop and run: git rm --cached .env

# 4. Make the initial commit
git commit -m "feat: initial commit — NeuroFlux autonomous content pipeline"

# 5. Add your GitHub remote (replace with your actual repo URL)
git remote add origin https://github.com/<your-username>/NeuroFlux.git

# 6. Push
git branch -M main
git push -u origin main
