# ref
Ref is a lightweight command-line reference manager. It is built on python and vim. 

Ref is released under the terms of the MIT license.

# Installation
## Prerequesites
You'll need a recent vim, compiled with python 2.7 support.

On ubuntu the ones in `apt-get` will do,
on Mac OS X use `brew install python` and `brew install vim`.
On Mac OS X you'll also need poppler for the pdftotext command line tool: `brew install poppler`

## Installation
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
"Cookie"    : "<<Obtained from visiting google scholar with Live HTTP headers>>"
}
```

Setting your base\_dir to a dropbox folder will enable automatic syncing between your Dropbox-enabled computers.
The database and pdf's will be saved in the base\_dir.

The Cookie you'll have to set manually after you added a few document and google scholar will
start blocking the randomly generated cookies; you can skip this for now.

* Go to scholar.google.com, search for something
* On the search results, go to settings > Bibliography manager > Show links to import citations into BibTeX
* Do another search on scholar.google.com and with Live HTTP headers capture the Cookie

# Usage
Type "ref" on the command line to see the main screen which is a vim session with two panes, split horizontally.
Move around like usual in vim with hjkl and jump between the panes with ctrl+W+W

* `:Add rel/path/to/downloaded/pdf` will add the document and fetch the bibtex from google scholar based on the title from the document.
* `:Fetch` if the fetched bibtex was wrong, fix the title then type `:Fetch` to try again.
* Search by typing `//keyword` where the keyword could be an author name or words from the title.
* To clear a search just enter `//` (i.e. search without any keyword)
* You can still use vim's regular search with `/keyword`

# Pro tips
You're already a pro.
