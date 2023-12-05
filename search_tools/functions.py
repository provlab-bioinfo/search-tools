import os, re, ahocorasick, pickle, glob, random, copy, shutil, logging, errno, hashlib, gzip
import pandas as pd
from pathlib import Path
from contextlib import suppress
from alive_progress import alive_bar
from itertools import chain
from collections import defaultdict

def findFile(regex):
    """Simple finder for a single file
    :param regex: The regex for the file
    """    
    return(glob.glob(regex, recursive = True))

def generateMLookupDB(dir: str, outDir: str, excludeDirs: list[str] = None):
    """ Generates a mlocate.db database for indexed searching
    :param dir: The directory to search
    :param outDir: the file to save database to
    :param excludeDirs: Directories to omit
    """       
    updatedb = "updatedb --database-root '" + dir + "' --output '" + outDir + "'"
    if excludeDirs != None: updatedb = updatedb + ' --prunepaths "' + " ".join(excludeDirs) + '"'
    os.system(updatedb)

def mlocateFile(file, mLocateDB):
    import subprocess
    command = "locate --database '" + mLocateDB + "' --nofollow '" + file + "'"
    try:
        return(subprocess.check_output(command, shell=True, text=True))
    except subprocess.CalledProcessError:
        return(None)   

def generateFlatFileDB(dir: list[str],  outFile: str = None, overwrite = False, verbose = True):
    """Retrieves all files within a specified folder.
    :param dir: Directory(ies) to search
    :param outFile: The output file path
    :param overwrite: Overwrite outFile if it exists
    :param verbose: Show progress bar
    :return: A list of files, or the path to the output DB file
    """
    # TODO: Parse input dirs and remove any child directories
    paths = [dir] if isinstance(dir, str) else dir
    for path in paths:
        if not os.path.exists(path): raise Exception("Directory '" + path + "' does not exist. Cannot generate database.")
    if (overwrite == False and outFile is not None and os.path.exists(outFile)): 
        print("DB already exists and overwrite = False. Retrieving existing DB...")
        return outFile
    out = [] if outFile is None else open(outFile,'w')

    with alive_bar(title="Retrieving files...", unknown="dots_waves", disable = not verbose) as bar: 
        for root, dirs, files in chain.from_iterable(os.walk(path) for path in paths):
            for item in files + dirs:           
                found = os.path.join(root, item)          
                out.write(found + "\n") if outFile is not None else out.append(found)
                bar()
            

    if outFile is not None: out.close()
    return (out if outFile is None else outFile)

# printFound = lambda nFiles, nFound, speed, end="\r": print("   Parsed {} files and found {} files ({}s)                 ".format(nFiles,nFound,speed),end=end)
# def generateFlatFileDB(dir: str, regex: str = None, fileExt: str = None, outFile: str = None, overwrite = False, maxFiles:int = 100000000, excludeDirs: list[str] = [], verbose: bool = True):
#     """Finds all files that fit a regex in a specified folder
#     :param dir: Directory to search
#     :param regex: The regex to search by. Cannot be used with fileExt
#     :param fileExt: The file extension to include. Cannot be used with regex
#     :param outFile: The output file path
#     :param maxFilesRead: The maximum number of files to read, defaults to 100000000
#     :param excludeDirs: List of folders to exclude
#     :param verbose: Print progress messages?, defaults to True
#     """
#     nFound = nFiles = speed = 0
#     out = []
#     lastCheck = startTime = time.time()
#     excludeDirs = "|".join(excludeDirs)

#     if not os.path.exists(dir):
#         raise Exception("Directory '" + dir + "' does not exist. Cannot generate database.")

#     if (overwrite == False and outFile is not None and os.path.exists(outFile)):
#         return outFile

#     if outFile is not None:
#         out = open(outFile,'w')

#     if (verbose): print("Populating database...")

#     for root, dirs, files in os.walk(dir, topdown=True):
#         dirs.sort(reverse=True)
#         if nFound >= maxFiles: break
#         for file in files + dirs:
#             nFiles += 1
#             match = True
#             if (fileExt is not None or regex is not None):
#                 match = file.endswith((fileExt)) if (regex is None) else re.match(regex, file)            
#             if match:
#                 #if re.search(excludeDirs, root) != None: continue
#                 path = str(root) + "/" + str(file)
#                 if outFile is not None: 
#                     out.write(path + "\n")
#                 else: 
#                     out.append(path)
#                 nFound += 1
#             if (nFiles % 1000 == 0): 
#                 speed = str(round(1000/(time.time() - lastCheck)))
#                 lastCheck = time.time()
#             if (verbose): printFound(nFiles,nFound,speed)

#     if (verbose): printFound(nFiles,nFound,str(round(time.time() - startTime,2)),"\n")
#     return (out if outFile is None else outFile)

def searchFlatFileDB(db: str = None, outFile: str = None, searchTerms: list[str] = [], includeTerms: list[str] = [], excludeTerms: list[str] = [], caseSensitive = False, verbose = True):
    """Searches a flat file database. 
    :param db: The path to the flat file database generated by generateFlatFileDB
    :param outFile: The path to save the subset database in, will output list otherwise
    :param searchTerms: Strings that paths must include
    :param includeTerms: Strings that paths must include at least one of 
    :param excludeTerms: Strings that paths must not include
    :param caseSensitive: Is case important?, defaults to False
    :param verbose: Print progress messages?, defaults to True
    """
    #TODO: Remove the error/exclamation marks from the progress bars
    searchTerms = [searchTerms] if isinstance(searchTerms, str) else searchTerms
    includeTerms = [includeTerms] if isinstance(includeTerms, str) else includeTerms
    excludeTerms = [excludeTerms] if isinstance(excludeTerms, str) else excludeTerms

    if isinstance(db, str): db = set(open(db))

    db = {str(file).strip() for file in db}

    # Keep by searchTerms
    if (len(searchTerms)):
        automatons = [generateSearchAutomaton(term, caseSensitive = caseSensitive) for term in searchTerms]
        out = set()
        with alive_bar(total = len(db), title="Checking for search terms....", unknown="dots_waves", disable = not verbose) as bar:
            for file in set(db):
                f = f"^{file}$"
                add = [next(automaton.iter(f if caseSensitive else f.lower()),False) for automaton in automatons]         
                if all(add): 
                    out.add(file)
                    bar()
        db = copy.deepcopy(out)

    # Keep by includeAutomaton
    if (len(includeTerms)):
        includeAutomaton = generateSearchAutomaton(includeTerms, caseSensitive = caseSensitive)
        out = set()
        with alive_bar(total = len(db), title="Checking for include terms...", unknown="dots_waves", disable = not verbose) as bar:
            for file in set(db):
                f = f"^{file}$"
                if (next(includeAutomaton.iter(f if caseSensitive else f.lower()),False)): 
                    out.add(file)
                    bar()
        db = copy.deepcopy(out)

    # Remove by excludeTerms
    if (len(excludeTerms)):
        excludeAutomaton = generateSearchAutomaton(excludeTerms, caseSensitive = caseSensitive)
        out = copy.deepcopy(db)
        with alive_bar(total = len(db), title="Checking for exclude terms...", unknown="dots_waves", disable = not verbose) as bar:
            for file in set(out):             
                if (next(excludeAutomaton.iter(file if caseSensitive else file.lower()),False)): 
                    db.discard(file)
                else:
                    bar()

    db = list(db)

    if (outFile is not None):
        with open(outFile, 'w') as f:
            for line in db:
                f.write(f"{line.strip()}\n")

    return (db if outFile is None else outFile)

def filterFileClass(db: list, classToFilter: str, inclusive:bool = False):
    """Remove either files/folders from list output from generateFlatFileDB.
    :param db: list output from generateFlatFileDB
    :param classToFilter: the type of file to remove (either 'file', 'folder', or 'symlink')
    :param inclusive: Should search be inclusive or exclusive?
    """
    if classToFilter not in ['file', 'folder', 'symlink']:
        raise ValueError("Invalid choice for 'fileType'. Choose either 'file', 'folder', or 'symlink'.")

    if isinstance(db, str): db = set(open(db))
    db = {str(file).strip() for file in db}
    files = set()

    if classToFilter == 'file': 
        files = {path for path in db if os.path.isfile(path)}
    elif classToFilter == 'folder': 
        files = {path for path in db if os.path.isdir(path)}
    elif classToFilter == 'symlink': 
        files = {path for path in db if os.path.islink(path)}

    return list(files) if inclusive else list(db.difference(files))

def findOrRemoveEmptyDirs(baseFolder: str, remove=False):
    """Finds a list of empty directories, removes them if desired.
    :param baseFolder: search through this folder
    :param remove: whether or not empty directories should be removed
    """
    empty_dirs = []
    for dirpath, dirnames, filenames in os.walk(baseFolder, topdown=False):
        if not dirnames and not filenames:
            empty_dirs.append(dirpath)
            if remove: os.rmdir(dirpath)
    return empty_dirs if not remove else None
    
def findNestedDirs(baseFolder: str):
    """Finds folders with unnecessary nesting.
    :param baseFolder: search through this folder
    """
    nested_dirs = []

    items = os.listdir(baseFolder)

    if len(items) == 1 and os.path.isdir(os.path.join(baseFolder, items[0])):
        nested_folder = os.path.join(baseFolder, items[0])
        nested_dirs.append(nested_folder)
    
    # Recursive check for sub-folders
    for item in items:
        item_path = os.path.join(baseFolder, item)
        if os.path.isdir(item_path):
            nested_dirs.extend(findNestedDirs(item_path))

    return nested_dirs

def flattenDirectory(directory: str, excludeDirs: list[str] = []):
    """Flatten a single nested directory.
    :param directory: The directory to flatten.
    """
    dir_name = os.path.basename(directory)
    if dir_name in excludeDirs: 
        return

    # Handle symbolic links
    parent_dir = os.path.dirname(directory)
    if os.path.islink(directory):
        os.unlink(directory)
        return

    try:
        nested_items = os.listdir(directory)
    except FileNotFoundError:
        logging.info(f"Flattening directory failed due to {directory} not found")
    for item in nested_items:
        src_path = os.path.join(directory, item)
        dest_path = os.path.join(parent_dir, item)

        # Check if destination path already exists (parent folder of same name like all/all/)
        if os.path.exists(dest_path):
            # Rename using a counter
            base, ext = os.path.splitext(item)
            counter = 1
            while os.path.exists(dest_path):
                item = f"{base}_{counter}{ext}"
                dest_path = os.path.join(parent_dir, item)
                counter += 1
        shutil.move(src_path, dest_path)
    os.rmdir(directory)

def flattenAndPruneDirectory(directory: str):
    """Utility function to iteratively flatten nesting + remove empty dirs.
    :param directory: directory to clean.
    """
    nested_dirs = findNestedDirs(directory)[::-1] # Get in reverse order to process bottom-up
    for dir in nested_dirs: flattenDirectory(dir)
    while findOrRemoveEmptyDirs(directory):
        findOrRemoveEmptyDirs(directory, remove=True)

def findDuplicateFileNames(paths: list[str] = []):
    """Find files with identical filenames under different directories.
    :param paths: a list of paths.
    :return: a dictionary where keys are filenames and values are lists of directories where the file was found.
    """
    file_map = defaultdict(list)
    for path in paths:
        directory, filename = os.path.split(path)
        file_map[filename].append(directory)
    # Filter out filenames that only appear in one directory
    duplicates = {filename: dirs for filename, dirs in file_map.items() if len(dirs) > 1}
    return duplicates


def generateSearchAutomaton(searchTerms:list[str], file:str = None, caseSensitive = False):
    """Generates a search automaton for Aho-Corasick search
    :param searchTerms: A list of search terms
    :param file: An optional output file to pickle into
    :return: An automaton or the path to the pickle
    """
    if not isinstance(searchTerms, list): searchTerms = [searchTerms]
    searchTerms = [str(term) for term in searchTerms]
    if (not caseSensitive): searchTerms = [term.lower() for term in searchTerms]
    automaton = ahocorasick.Automaton()
    for term in searchTerms:
        automaton.add_word(term, term)
    automaton.make_automaton()

    if (file is not None):
        with open(file, "wb") as f:
            pickle.dump(automaton, f)
        return f
    else:
        return automaton

def moveFileInTree(file:str, sourceDir:str, destDir:str):
    """Moves a file in a tree between two directories.
    :param file: The path to the file to move
    :param sourceDir: The source directory
    :param destDir: The destination directory
    :raises FileNotFoundError: Target file does not exist
    :raises FileNotFoundError: Target file does not exist in the source directory
    """
    if not os.path.exists(file): raise FileNotFoundError(f"Cannot move file. '{file}' does not exist.")       
    if (sourceDir not in file): raise FileNotFoundError(f"Cannot move file. '{file}' is not in {sourceDir}.")
    if os.path.islink(file): os.unlink(file)
    parentDir = str(Path(file).parent)
    newFile = file.replace(sourceDir.strip("//"), destDir.strip("//"))
    if (os.path.isfile(file)):
        Path(newFile).parent.mkdir(parents = True, exist_ok = True)
        shutil.move(file, newFile)
    elif (os.path.isdir(file)):
        parentDir = file
        Path(newFile).mkdir(parents = True, exist_ok = True)
    with (suppress(OSError)): os.rmdir(parentDir)
            
def computeMD5(filename):
    """Compute the md5sum of a file."""
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            md5.update(chunk)
    return md5.hexdigest()

def compressFile(filename):
    """Compress a file using gzip and return the path to the compressed file."""
    compressed_filename = filename + ".gz"
    with open(filename, 'rb') as f_in, gzip.open(compressed_filename, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(filename)
    return compressed_filename


def sampleAndCopyFiles(rootSource: str, rootDest: str, numFiles=1000, dry_run=True):
    """Sub-sample and copy files of a directory to a destination while keeping the directory structure.

    :param rootSource: directory to sub-sample and copy
    :param rootDest: destination where files will be copied to
    :param numFiles: number of files to sub-sample
    """
    all_files = generateFlatFileDB(rootSource)
    
    # Randomly select files
    selected_files = random.sample(all_files, min(numFiles, len(all_files)))
    
    # Copy selected files to destination, maintaining directory structure
    for file_path in selected_files:
        # Compute destination path
        relative_path = os.path.relpath(file_path, rootSource)
        dest_path = os.path.join(rootDest, relative_path)

        # Create destination directory if it doesn't exist
        dest_dir = os.path.dirname(dest_path)
        if dry_run:
            print(f"Would create directory: {dest_dir}")
        else:
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
        
        if os.path.isfile(file_path):
            # Copy the file
            if dry_run:
                print(f"Would copy {file_path} to {dest_path}")
            else:
                shutil.copy2(file_path, dest_path)
        else:
            print(f"Skipping {file_path} because it's not a file.")

def splitFolder(files:list[str], sourceDir: str, destDir:str, dry_run=True, log_file=None):
    """Splits a folder into two directories based on search criteria

    Potential cases to worry about:
        - symlinks: can either recreate the symlink or copy as is. shutil should handle the latter
        - permission errors

    :param sourceDir: the source directory
    :param targetDir: the output directory
    :param verbose: Print progress messages?, defaults to True
    :param inverse: If true, move all files that do not match search criteria (ie. opposite behaviour)
    """
    logging.basicConfig(filename=log_file if log_file else None, level=logging.INFO)

    if log_file: 
        logging.basicConfig(filename=log_file, level=logging.INFO)
    else: 
        logging.basicConfig(level=logging.INFO)

    # Check if all the input files are in the sourceDir
    origFiles = files
    files = set()
    for file in origFiles:
        if (sourceDir not in file): 
            logging.error(f"File {file} is not in the source directory. Skipping...")
        else:
            files.add(file)

    # Create parent folders
    parentDirs = set([str(Path(file).parent) for file in files])
    for parentDir in parentDirs:
        newDir = Path(str(parentDir).replace(sourceDir.strip("//"), destDir.strip("//")))
        if logging: 
            logging.info(f"Creating {newDir}")
        if not dry_run:            
            newDir.mkdir(parents = True, exist_ok = True)
   
    # Move files
    files = {file for file in files if not os.path.isdir(file)}
    for file in files:
        try:
            newFile = file.replace(sourceDir.strip("//"), destDir.strip("//"))
            if os.path.islink(file): 
                linkto = os.readlink(file)
                if (linkto in files): # Updates symlink if the target file is being moved as well
                    linkto = linkto.replace(sourceDir.strip("//"), destDir.strip("//"))
                os.symlink(linkto, newFile)
                os.remove(file)
            else:                
                if logging:
                    logging.info(f"Moving {file} to {newFile}")
                if not dry_run:
                    shutil.move(file, newFile)
        except PermissionError:
            logging.error(f"Permission denied while trying to move {file}. Skipping...")
        except shutil.Error as e:
            logging.error(f"An error occured while trying to move {file}: {str(e)}. Skipping...")

    # Clean-up old directories. Delete if empty, leave if not    
    parentDirs = [str(dir) for dir in list(parentDirs)]
    for dir in sorted(parentDirs, key=len)[::-1]: 
        if (log_file): logging.info(f"Deleting {dir}")
        if not dry_run: 
            try:
                os.rmdir(dir)
            except FileNotFoundError: 
                logging.error(f"Could not find directory {dir} for deletion. Skipping...")
            except OSError: 
                logging.error(f"Could not delete directory {dir} as it is not empty. Skipping...")

def expandZipFlatFileDB(file: str):
    import zipfile, tempfile, shutil

    with open(file,"r") as infile:
        with tempfile.NamedTemporaryFile(mode="w", delete = False) as tempFile:
            for line in infile.readlines():
                zip = zipfile.ZipFile(str.strip(line))
                names = zip.namelist()
                tempFile.write(line)
                [tempFile.write(str.strip(line) + "/" + name + "\n") for name in names]

            tempFile.close()
            infile.close()
            os.remove(file)
            shutil.move(tempFile.name, file)

def generateDirTree(dir: list[str], outFile:str = None, startIndex:int = 1):
    """ Generates an indexed representation of a directory tree
    :param path: The folder to create the directory for
    :param outFile: The output CSV file
    :param startIndex: The start index number
    :return: Dataframe of trees
    """
    fileIndexCol = "fileIndex"
    fileNameCol = "fileName"
    pathCol = "path"
    fileTypeCol = "type"
    fileSizeCol = "size"
    if isinstance(dir, str): dir = [dir] # Coerce str to list   

    # Create tree with a pre-fixed index
    def pathToDict(path, idx):
        file_token = ''
        for root, dirs, files in os.walk(path):
            files = sorted(files,  key=lambda s: re.sub('[-+]?[0-9]+', '', s)) # Sort but ignore numbers
            tree = {(str(idx) + "." + str(idx1+1) + "|" + d): pathToDict(os.path.join(root, d),str(idx) + "." + str(idx1+1)) for idx1, d in enumerate(dirs)}
            tree.update({(str(idx) + "." + str(idx2+1+len(dirs)) + "|" + f): file_token for idx2, f in enumerate(files)})
            return tree

    # Flatten the keys
    def getKeys(dl, keys=None):
        keys = keys or []
        if isinstance(dl, dict):
            keys += dl.keys()
            _ = [getKeys(x, keys) for x in dl.values()]
        elif isinstance(dl, list):
            _ = [getKeys(x, keys) for x in dl]
        return list(set(keys))

    #
    def keysToPaths(keys, path, idx):

        keys = [str(idx) + "|" + os.path.basename(path)] + keys
        paths = pd.DataFrame(keys, columns=[pathCol])
        paths[[fileIndexCol, fileNameCol]] = paths[pathCol].apply(lambda x: pd.Series(str(x).split("|")))
        sort = sorted(paths[fileIndexCol], key=lambda x: [int(y) for y in x.split('.')])
        paths = paths.set_index(fileIndexCol).reindex(sort).reset_index().drop(columns=[pathCol])
        paths[[pathCol]] = path
        return (paths)

    def addDirectoryNames(paths):
        for index, row in paths.iterrows():
            if (index == 0): continue
            parentIdx = os.path.splitext(row[fileIndexCol])[0]
            parentRow = paths.loc[paths[fileIndexCol] == parentIdx]
            paths.at[index,pathCol] = parentRow.iloc[0][pathCol] + "/" + row[fileNameCol]
        return (paths)

    def addFileTypes(paths):
        def custom_ext(name):
            root, ext = os.path.splitext(name)
            if ext == '.gz':
                root, prev_ext = os.path.splitext(root)
                ext = prev_ext + ext
            return ext if ext else "Folder"

        paths[fileTypeCol] = paths[fileNameCol].apply(custom_ext)
        #paths[fileTypeCol] = paths[fileNameCol].apply(lambda name: "Folder" if (os.path.splitext(name)[1] == "") else os.path.splitext(name)[1][1:])
        return(paths)

    def addFileSize(paths):
        paths[fileSizeCol] = paths[pathCol].apply(lambda path: float("{:.3f}".format(os.stat(path).st_size / (1024 * 1024))))
        return (paths)

    # Parse to dataframe
    def pathToDF(path, idx):
        dic = pathToDict(path, idx)
        keys = getKeys(dic)
        paths = keysToPaths(keys,path,idx)
        paths = addDirectoryNames(paths)
        paths = addFileTypes(paths) 
        paths = addFileSize(paths)       
        return paths

    trees = pd.DataFrame()
    for idx,path in enumerate(dir):
        print(path)
        tree = pathToDF(path, idx+startIndex)
        if outFile is None:
            trees = pd.concat([trees,tree], ignore_index=True)
        else:
            tree.to_csv(outFile, mode='w' if (idx == 0) else 'a', header= (idx == 0))

    return (trees if outFile is None else outFile)

def listSubDir(dir: list[str], absolutePath: bool = True, onlyDirs: bool = True, minFolders: int = 2, traverseOrphanDirs: bool = False):
    """Lists all subdirectories in a path. If given a list, all subdirectories for all paths.
    :param path: The parent folder(s)
    :param absolutePath: Return the absolute path?, defaults to True
    :param onlyDirs: Return only directorys, excludes files, defaults to True
    :param minFolders: Continue traversing if few folders exist?, defaults to 2
    :param traverseOrphanDirs: If a folder only contains a single folder, should I traverse through that folder?, defaults to False
    :return: All paths to the subfolders
    """    
    def traverseOrphanFolder(path:str):
        subpaths = list(os.scandir(path))
        if (len(subpaths) == 1):
            if (subpaths[0].is_dir()):
                return traverseOrphanFolder(subpaths[0].path)
        return path

    subpaths = ""
    if (type(dir) == str):
        if onlyDirs: 
            subpaths = [f.path for f in os.scandir(dir) if f.is_dir()]
            #print(subpaths)
            if (traverseOrphanDirs): subpaths = [traverseOrphanFolder(f) for f in subpaths]
            #print(subpaths)
        else: subpaths = [f.path for f in os.scandir(dir)]
        if absolutePath == False: subpaths = [os.path.basename(subpath) for subpath in subpaths]
    elif (type(dir) == list): 
        subpaths = [listSubDir(p, absolutePath, minFolders) for p in dir]
        subpaths = sum(subpaths,[])
        subpaths = [subpath + "/" for subpath in subpaths]
    else:
        return []
    return subpaths

def str_search(pattern:str, input:list[str], trim:bool = True):
    """Searches a string to see if a specific pattern is present
    :param pattern: Regular expression to search with
    :param input: The string to search
    :param trim: Remove the None values, defaults to True
    :return: The strings that matched the pattern
    """    
    matches = None
    if (type(input) == str):
        matches = re.search(pattern, input)
        matches = None if matches == None else matches.string
    elif (type(input) == list):
        matches = [str_search(pattern, s) for s in input]
        if (trim): matches = [m for m in matches if m != None]
    else:
        return None
    return matches
             
def str_extract(pattern, input, trim = True):
    """Extracts a specific pattern from a string
    :param pattern: Regular expression to search with
    :param input: The string to search
    :param trim: Remove the None values, defaults to True
    :return: The strings that matched the pattern
    """    
    matches = None
    if (type(input) == str):
        matches = re.search(pattern, input)
        matches = None if matches == None else matches.group(0)
    elif (type(input) == list):
        matches = [str_extract(pattern, s) for s in input]
        if (trim): matches = [m for m in matches if m != None]
    else:
        return None
    return matches
             
def parseExtensions(dir: str, maxFiles = 100000): 
    """Gets all extensions from a target directory
    :param targetDir: The path to the target directory
    :param maxFiles: If no new extensions are found after parsing `maxFiles` files, return
    :return: A list of the found extensions
    """    
    exts = set()
    n = 0
    for root, dirs, files in os.walk(dir):
        for filename in files:
            n += 1
            ext = os.path.splitext(filename)[1]
            if ext not in exts: 
                print("Added",ext)
                exts.add(ext)
                n = 0
        if (n > maxFiles): break    
    return(exts)

# def suctionBash(dir:list[str], excludeDirs: list[str]):
#     # Not working, some error with (  in the script "¯\_(ツ)_/¯ "
#     import textwrap
#     if isinstance(excludeDirs, str): excludeDirs = [excludeDirs]
#     excludeDirs = ",".join(excludeDirs)
#     script = textwrap.dedent("""
#         #!/bin/bash
#         SEARCHDIR=%s
#         EXCLUDEDIRS=%s
#         IFS=$'\\n' read -r -d '' -a EXCLUDEDIRS < <(awk -F',' '{ for( i=1; i<=NF; i++ ) print $i }' <<<"$EXCLUDEDIRS")
#         EXCLUDEARG=""

#         for DIR in "${EXCLUDEDIRS[@]}"; do
#             EXCLUDEARG+=' -not \( -path '"'*$DIR*' -prune \)"
#         done

#         EXCLUDEARG="${EXCLUDEARG:1}"

#         FINDFILES="find $SEARCHDIR -type f $EXCLUDEARG  -exec mv --backup=numbered {} $SEARCHDIR  2> /dev/null \;"
#         DELDIRS="find $SEARCHDIR/* -type d -exec rm -rf {} 2> /dev/null \;"

#         eval $FINDFILES
#         eval $DELDIRS
#         """ % (dir, excludeDirs))

#     os.system("bash -c '%s'" % script)

def suction(dir:list[str], excludeDirs: list[str] = []):
    """Moves all files within the specified directory to the root dir, then deletes all the folders
    :param dir: The directory to suction
    :param excludeDirs: A list of directories to ignore
    """    
    import shutil

    for root, dirs, files in os.walk(dir, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if d not in excludeDirs]
        if (root == dir): continue
        for file in files:
            filename = file
            idx = 1
            while (os.path.exists(os.path.join(dir, filename))):
                print(f"Duplicate file found for {file}")
                (name,ext) = os.path.splitext(file)
                filename = name + f".{idx}" + ext
            os.rename(os.path.join(root, file), os.path.join(root, filename))            
            shutil.move(os.path.join(root, filename), dir)

    [shutil.rmtree(os.path.join(dir,d)) for d in next(os.walk(dir))[1]]

def sigfig(val, n:int = 3):
    """Forces value to specific number of decimal points
    :param val: The value to format
    :param n: The number of decimal places
    :return: The truncated float
    """    
    return float('{0:.{1}f}'.format(float(val),n))

def sortDigitSuffix(data):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ] 
    return sorted(data, key=alphanum_key)

def importToDataFrame(filename, **kargs):
    """Generic importer to Pandas dataframes. Supports .csv, .tsv., .xlsx
    :param filename: The path to the file to import
    :param **kargs: Additional arguments to the Pandas read function
    :return: _description_
    """    
    ext = Path(filename).suffix
    df = pd.DataFrame()
    match ext:
        case ".tsv":
            df = pd.read_csv(filename, sep="\t", **kargs)
        case ".csv":
            df = pd.read_csv(filename, **kargs)
        case ".xlsx" | ".xlsm":
            df = pd.read_excel(filename, **kargs)
        case _:
            raise ImportError(f'Not able to parse extension "{ext}"')
    
    return df

def exportDataFrame(df, out, **kargs):
    """Generic exporter from Pandas dataframes. Supports .csv, .tsv., .xlsx
    :param filename: The path to the file to import
    :param **kargs: Additional arguments to the Pandas read function
    :return: _description_
    """    
    ext = Path(out).suffix
    match ext:
        case ".tsv":
            df.to_csv(out, sep="\t", **kargs)
        case ".csv":
            df.to_csv(out, **kargs)
        case ".xlsx":
            df.to_excel(out, **kargs)
        case _:
            df = out
    
    return out