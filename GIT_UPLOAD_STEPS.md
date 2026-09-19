# Git Upload Steps

Run these commands from inside the extracted `drylab-skills-and-code` directory.

## Upload to a new empty GitHub repository

```text
git init
git branch -M main
git status
git add .
git status
git commit -m "Add dry-lab skills and source code"
git remote add origin https://github.com/TEAM/REPOSITORY.git
git remote -v
git push -u origin main
```

Replace `TEAM` and `REPOSITORY` with the actual GitHub organization and repository name.

## Upload to an existing GitHub repository

Clone the existing repository first, copy the contents of this directory into that clone, then run:

```text
git status
git add .
git status
git commit -m "Add dry-lab skills and source code"
git push origin main
```

If the repository uses protected branches, create a working branch and open a pull request:

```text
git switch -c upload-drylab-code
git add .
git commit -m "Add dry-lab skills and source code"
git push -u origin upload-drylab-code
```

Do not place access tokens in repository files or command examples. Use the operating system credential prompt or an approved credential manager.
