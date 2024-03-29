# ref
Ref is a lightweight command-line reference manager. It is built on python and vim. 

Ref is released under the terms of the MIT license.

# Installation
## Preferred: Installation in dedicated conda environment
```
conda create -n ref
conda activate ref
conda install poppler vim ncurses -c conda-forge
git clone git@github.com:jzbontar/ref ref
cd ref
python setup.py develop
```

Replace the last line with `python setup.py install` if you don't want to change ref.

## Prerequesites (manual)
You'll need a recent vim, compiled with python support.

On ubuntu the ones in `apt-get` will do,
on Mac OS X use `brew install vim` which has python3 bindings.
On Mac OS X you'll also need poppler for the pdftotext command line tool: `brew install poppler`

## Installation (manual)
```
git clone https://github.com/jzbontar/ref.git
cd ref
python setup.py install
```

## Configuration
Set your base\_dir and google scholar Cookie in ~/.ref.conf, for example:

```
{
"base_dir"  : "~/Dropbox/ref",
"Cookie"    : "<<Obtained from request headers to google scholar, see below>>"
}
```

The database and pdf's will be saved in `base_dir`.
Setting your `base_dir` to a dropbox folder will enable automatic syncing between your Dropbox-enabled computers.

Obtaining the cookie:
* Go to scholar.google.com, search for something
* On the search results, go to settings > Bibliography manager > Show links to import citations into BibTeX
* In chrome, right click on page > Inspect > tab "Network" > click in list of html elements on page "scholar" > default tab "Headers" > section "Request Headers" > field "cookie"

# Usage
Type "ref" on the command line to see the main screen which is a vim session with two panes, split horizontally.
Move around like usual in vim with hjkl and jump between the panes with `ctrl+W+W`

* `:Add rel/path/to/downloaded/pdf` will add the document and fetch the bibtex from google scholar based on the title from the document.
* `:Fetch` if the fetched bibtex was wrong, fix the title then type `:Fetch` to try again.
* Search by typing `//keyword` where the keyword could be an author name or words from the title.
* To clear a search just enter `//` (i.e. search without any keyword)
* You can still use vim's regular search with `/keyword`
* Exit with `q`
* `ctrl+U` toggles the U flag (U for Unread)
* `:Delete` deletes document

# Screenshot
![screenshot](screeshot.png?raw=true)

# Pro tips
If you're switching from another reference manager or just a messy folder of pdfs,
you can open a python session, type `import ref; ref.init()` and `ref.import_dir(/path/to/your/messy/folder)`

The codebase consists of two files with less than 600LoC, it's easy to change things if needed.
