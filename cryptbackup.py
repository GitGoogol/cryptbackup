#!/usr/bin/env python3

# -*- coding: utf-8 -*-
"""
Created on Thu Dec 31 20:04:24 2020

@author: chris
"""

import os
import sys
import gnupg
import argparse
import platform
import shutil
import logging
import subprocess
import fnmatch

from pprint import pprint
from pathlib import Path
from datetime import datetime as dt, timedelta

ALGO = 'RSA4096'
RECENT_DIR_NAME = "recent"
periodUnits = {"level_2":"days", "level_3":"weeks", "level_4":"months"}  # possible: microseconds, milliseconds, seconds, minutes, hours, days, weeks, months, years
backupLevels = ("level_1", "level_2", "level_3", "level_4")
backupDirs = dict() #to store the directorys for the various backup levels
youngsters = dict() #to store the newest file for the various levels

#-----------------------------------------------------------------------------------------------------------
#--------------------------------------------------key stuf-------------------------------------------------
#-----------------------------------------------------------------------------------------------------------
def info_key(args):
    print("\n--------------------------List Keys-----------------------------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    print("----------------------------------------------------------------")
    print("\n")
    print("-----------------------List secret Keys-------------------------")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")
    print("----------------------------------------------------------------")


def generateKey(email, passphrase, path):
    retProc = subprocess.run(f"gpg2 --quick-gen-key --homedir {path} --batch --pinentry-mode loopback --passphrase {passphrase} {email} {ALGO} encr never", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    procOutput=retProc.stdout.decode("utf-8")
    pprint(procOutput)
    if(retProc.returncode==0):
        try:
            #todo: find a better way to extract fingerprint
            revocOutput = procOutput.splitlines()[-1]
            fingerprint = revocOutput.split("/")[-1].split(".")[0]
            print(f"Key generated with fingerprint: {fingerprint}")
            return fingerprint
        except:
            print("something went wrong with fingerprint extraction")
            exit()
    else:
        print(f"key gneration failed: {retProc.stdout}")
        exit()


def add_key(args):
    print("-------------Before key generation--------------------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")
    fingerprint = generateKey(args.email, args.passphrase, args.path)
    print("--------------After key generation-----------------list-keys----------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    print("--------------After key generation-----------------list-secret-keys---")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")

    args.fingerprint = fingerprint
    exportFile = f"priv_key_{fingerprint}.asc"
    status = export_key(args)
    if(status==0):
        print("\n\n\n--------------------------------------------------------------------------------------")
        print(f"private key exported to '{os.path.join(args.export_to, exportFile)}'")
        print(f"Key '{args.email}' generated with fingerprint '{args.fingerprint}'")
        print( "!!!!!!!!!!!!Do not forget to backup the key and remove it from the system!!!!!!!!!!!!!")
        print(f"-------------------{os.path.join(args.export_to, exportFile)}------------")


def export_key(args):
    exportFile = f"priv_key_{args.fingerprint}.asc"
    print("-------------Before key removal--------------------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    retProc = subprocess.run(f"gpg2 --homedir {args.path} --list-secret-keys", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if(retProc.stdout.decode("utf-8")==""):
        print("-----------E-R-R-O-R-------------")
        print("no secret-key available to export")
        print("--------no key exported----------")
        return 9999
    print(retProc.stdout.decode("utf-8"))
    print("---------export and delete secret keys--------------------------------")
    status = os.system(f"set -o noclobber && gpg2 -a --homedir {args.path} --batch --pinentry-mode loopback --passphrase {args.passphrase} --export-secret-keys {args.fingerprint} > {os.path.join(args.export_to, exportFile)}")
    if(status==0):
        print(f"private key exported to '{os.path.join(args.export_to, exportFile)}'")
        #for this command the fingerprint is needed
        os.system(f"gpg2 --homedir {args.path} --batch --yes --pinentry-mode loopback --passphrase {args.passphrase} --delete-secret-keys {args.fingerprint}")
        print("Removing private key from keyring...\n...\n...")
        print("---------------After key removal-------------------list-keys----------")
        os.system(f"gpg2 --homedir {args.path} --list-keys")
        print("---------------After key removal-------------------list-secret-keys---")
        print("----------nothing should be listed below------------------------------")
        os.system(f"gpg2 --homedir {args.path} --list-secret-keys")
    else:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"Key not exported. exit code: {status}")
        print(f"Check if '{os.path.join(args.export_to, exportFile)}' already exists. Overwriting is not supported with this command.")
        print(f"Check if key exists with the fingerprint '{args.fingerprint}'")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    
    return status
    

def remove_key(args):
    if(args.secretkey):
        status = os.system(f"gpg2 --homedir {args.path} --delete-secret-key {args.email}")
        if(status==0):
            print(f"Secret key '{args.email}' successfully removed.")
        else:
            print(f"key removal failed: exit code = '{status}'")

    status = os.system(f"gpg2 --homedir {args.path} --delete-key {args.email}")
    if(status==0):
        print(f"Key '{args.email}' successfully removed.")
    else:
        print(f"key removal failed: exit code = '{status}'")


    gpg = gnupg.GPG(homedir=args.path)
    remove_result = gpg.delete_keys(args.email)
    pprint(str(remove_result))
    

def import_key(args):
    status = os.system(f"gpg2 --homedir {args.path} --import {args.keyfile}")
    if(status==0):
        print(f"Key '{args.keyfile}' successfully imported.")
    else:
        print(f"import failed: exit code = '{status}'")
    
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")

    print("-------------------------------------------------------------------------------------------")
    print("Attention: propably the secret private key is now also in the keyring on the local machine!")
    print(f"Check output of command: 'gpg2 --homedir {args.path} --list-secret-keys'")
    print("-------------------------------------------------------------------------------------------")


#-----------------------------------------------------------------------------------------------------------
#--------------------------------------------------file stuf-------------------------------------------------
#-----------------------------------------------------------------------------------------------------------
def cleanupL4(keepFilesCount):
    logging.info(f"cleanup Level 4 and keep {keepFilesCount} files")
    l4Files = os.listdir(backupDirs["level_4"])
    l4Count = len(l4Files)
    logging.info(f"Available file count = {l4Count}")
    if(l4Count>keepFilesCount):
        for file in sorted(l4Files)[:-keepFilesCount]:
            os.remove(os.path.join(backupDirs["level_4"], file))
            logging.info(f"cleanup Level 4: '{file}' deleted.")
    else:
        logging.info("cleanup Level 4: no files to delete.")


def cleanupLevel(level, before_ts):
    logging.info(f"delete files in '{level}' older than '{before_ts}'")
    for file in os.listdir(backupDirs[level]):
        file_ts = dt.strptime(file.split("_")[0], "%Y-%m-%d-%H-%M-%S")
        if(file_ts < before_ts):
            os.remove(os.path.join(backupDirs[level], file))
            logging.info(f"'{file}' with ts:'{file_ts}' deleted in '{level}'")

    
def doMovement(from_level, to_level, period):
    unit = periodUnits[to_level]
    if(unit == "months"):
        period = period * 4
        unit = "weeks"
    elif(unit == "years"):
        period = period * 52
        unit = "weeks"

    timedelta_kw = {unit:period}
    diff_time = timedelta(**timedelta_kw)
    logging.info(f"time difference for moving action: '{diff_time}'")

    file_diff = youngsters[from_level][1] - youngsters[to_level][1]
    if(file_diff > diff_time):
        logging.info(f"File time diff: '{from_level}': '{youngsters[from_level][1]}' - '{to_level}': '{youngsters[to_level][1]}' = '{file_diff}'")
        srcFile = os.path.join(backupDirs[from_level], youngsters[from_level][0])
        shutil.move(srcFile, backupDirs[to_level])
        logging.info(f"moved file '{srcFile}' to '{backupDirs[to_level]}'")
        return True
    else:
        logging.info(f"nothing to move from '{from_level}' to '{to_level}'")
        return False


def getYoungsters():
    for level in backupLevels:
        backupFiles = os.listdir(backupDirs[level])
        youngster = sorted(backupFiles)[-1]
        string_ts = youngster.split("_")[0]
        youngster_ts = dt.strptime(string_ts, "%Y-%m-%d-%H-%M-%S")
        youngsters[level] = (youngster, youngster_ts)
        logging.info(f"Youngest file in '{backupDirs[level]}': '{youngster}'")


def doInitialSetup(cryptedFile):
    if(not any(os.scandir(backupDirs["level_4"]))):
        shutil.copy(cryptedFile, backupDirs["level_4"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_4']}'")
        return False
    elif(not any(os.scandir(backupDirs["level_3"]))):
        shutil.copy(cryptedFile, backupDirs["level_3"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_3']}'")
        return False
    elif(not any(os.scandir(backupDirs["level_2"]))):
        shutil.copy(cryptedFile, backupDirs["level_2"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_2']}'")
        return False
    elif(not any(os.scandir(backupDirs["level_1"]))):
        shutil.copy(cryptedFile, backupDirs["level_1"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_1']}'")
        return False
    else:
        logging.info("Initial Setup already done.")
        return True


def encryptFile(file, keyName, keyDir, testmode):
    outputPath, fileName = os.path.split(file)
    if(testmode):
        try:
            l1_youngster = dt.strptime(sorted(os.listdir(backupDirs["level_1"]))[-1].split("_")[0], "%Y-%m-%d-%H-%M-%S")
            ts = (l1_youngster + timedelta(days=1)).strftime("%Y-%m-%d-%H-%M-%S")
        except:
            print("before running the test mode you have to run at least 4 times in normal mode.")
            exit()
    else:
        ts = dt.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    outputFile = os.path.join(outputPath, RECENT_DIR_NAME, f"{ts}_{fileName}.gpg")
    status = os.system(f"gpg2 --homedir {keyDir} -o {outputFile} -e -r {keyName} {file}")
    if(status==0):
        logging.info(f"File '{file}' encrypted with key '{keyName}' from '{keyDir}' -> '{outputFile}'")
    else:
        logging.info (f"encryption status: nok; exit code = '{status}'")

    return outputFile


def checkDestination(destPath):
    for level in backupLevels:
        backupDirs[level] = os.path.join(destPath, level)

        if(not os.path.isdir(backupDirs[level])):
            os.makedirs(backupDirs[level])
        logging.info(f"'{level}' dir: '{backupDirs[level]}'")
    
    recentDir = os.path.join(destPath, RECENT_DIR_NAME)
    shutil.rmtree(recentDir, ignore_errors=True)
    os.makedirs(recentDir)
    logging.info(f"'{RECENT_DIR_NAME}' dir: 'recentDir'")


def get_source_file(strPath, pattern):
    if(os.path.isfile(strPath)): return strPath
    elif(os.path.isdir(strPath)):
        dirList = os.scandir(strPath)
        fileList = [file for file in dirList if file.is_file() and fnmatch.fnmatch(file.name, pattern)]
        return os.path.abspath(max(fileList, key=os.path.getctime))
    else:
        print(f"'{strPath}' is not a file nor a directory, so nothing to backup")
        exit()

def backup_handling(args):
    #new concept
    #vier Ordner L1(Tagesbackups), L2(älter als x Tage), L3(älter als x Wochen) und L4(älter als x Monate)
    #Kopiere src in L1 als src_<dt>
    #wenn Ordner im nächsten Level leer, schiebe File dorthin (wiederhole bis zum letzten Level)
    #wenn File in level_x um x (days, weeks, months,.. je nach level) älter als jüngstes File im nächsten Level level_x+1, schiebe File dorthin
    #wenn File in nächstes Level geschoben, lösche im aktuellen Level alle Files die älter sind als jüngstes File im nächsten Level vor dem Verschieben
    
    checkDestination(args.dst)
    srcFile = get_source_file(args.src, args.pattern)

    if(args.copy):
        tmpFile = shutil.copy(srcFile, args.dst) #copy the file in the root to encrypt and move it afterwards
    else:
        tmpFile = shutil.move(srcFile, args.dst) #move the file in the root to encrypt and move it afterwards

    cryptedFile = encryptFile(tmpFile, args.email, args.path, args.test)
    os.remove(tmpFile)

    if(doInitialSetup(cryptedFile) == False):
        exit()
    else:
        shutil.copy(cryptedFile, backupDirs["level_1"])
    
    getYoungsters()

    for level in range(0, len(backupLevels)-1):
        moveDone = doMovement(backupLevels[level], backupLevels[level+1], args.period)
        if(moveDone):
            cleanupLevel(backupLevels[level], youngsters[backupLevels[level+1]][1])
            if(backupLevels[level+1] == "level_4"):
                cleanupL4(args.delete)
        else:
            exit()

 
def restore_handling(args):
    status = os.system(f"gpg2 --homedir {args.path} -u {args.email} -o {args.dst} -d {args.src}")
    if(status==0):
        print(f"File '{args.src}' successfully decrypted and stored to '{args.dst}'")
    else:
        print(f"restore failed: exit code = '{status}'")


if __name__ == '__main__':
    if platform.system() != 'Linux':
        print (f'Platform {platform.system()} not suported.')
        exit()
    
    appPath = os.path.dirname(sys.argv[0])
    homeDir = os.path.expanduser("~")
    logFile = os.path.join(homeDir, "cryptbackup.log")
    logging.basicConfig(filename=logFile,level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%d.%m.%Y %H:%M:%S')
    logging.info("-------------------------------------------------------Start new backup run-------------------------------------------------------")

    keyDir = Path.home().as_posix() + "/.gnupg"

    main_parser = argparse.ArgumentParser(description="A tool to do encrypted backups of a single file.")
    subparsers = main_parser.add_subparsers(title="subcommands", dest="sub_func", required=True, description="type subcommand -h to get help", help="additional help")

    infokey_parser = subparsers.add_parser("key_info", help="get key infos")
    infokey_parser.add_argument('--path', default=keyDir, help=f"where is the keyring the key should get imported to (default: '{keyDir}')")
    infokey_parser.set_defaults(func=info_key)

    addkey_parser = subparsers.add_parser("add_key", help="generate key and export the secret key")
    addkey_parser.add_argument('--path', default=keyDir, help=f"where should the key get stored (default: '{keyDir}')")
    addkey_parser.add_argument('--export_to', default=homeDir, help=f"where to export the private key file (default: '{homeDir}'")
    addkey_parser.add_argument('email', help="keyname,... email in most cases. IMPORTANT: put email in single quotes!!!")
    addkey_parser.add_argument('passphrase', help="passphrase. IMPORTANT: put passphrase in single quotes!!!")
    addkey_parser.set_defaults(func=add_key)
  
    remkey_parser = subparsers.add_parser("remove_key", help="remove key")
    remkey_parser.add_argument('--path', default=keyDir, help=f"where is the key to remove stored (default: '{keyDir}')")
    remkey_parser.add_argument('--secretkey', action='store_true', help="delete also secret-key")
    remkey_parser.add_argument('email', help="keyname,... email in most cases")
    remkey_parser.set_defaults(func=remove_key)

    impkey_parser = subparsers.add_parser("import_key", help="import key")
    impkey_parser.add_argument('--path', default=keyDir, help=f"where is the keyring the key should get imported to (default: '{keyDir}')")
    impkey_parser.add_argument('keyfile', help="the keyfile to import")
    impkey_parser.set_defaults(func=import_key)

    expkey_parser = subparsers.add_parser("export_key", help="export key and just keep the public key in the keyring")
    expkey_parser.add_argument('--path', default=keyDir, help=f"where is the keyring the key should get imported to (default: '{keyDir}')")
    expkey_parser.add_argument('--export_to', default=homeDir, help=f"where to export the key file (default: '{homeDir}'")
    expkey_parser.add_argument('fingerprint', help="get the fingerprint of the key by running the key_info command.")
    expkey_parser.add_argument('passphrase', help="passphrase. IMPORTANT: put passphrase in single quotes!!!")
    expkey_parser.set_defaults(func=export_key)

    bckp_parser = subparsers.add_parser("backup", help="backup stuff")
    bckp_parser.add_argument('src', help="path to the source file; giving just a path takes the most recent file to backup.")              
    bckp_parser.add_argument('dst', help="path to the destination folder")          
    bckp_parser.add_argument('email', help="keyname,... email in most cases")   
    bckp_parser.add_argument('--pattern', default='*', help="only considered if src is a path; use a pattern as in pyhton fnmatch described")   
    bckp_parser.add_argument('--copy', action='store_true', help="copy the src file instead of moving it")   
    bckp_parser.add_argument('--path', default=keyDir, help=f"where is the key stored (default: '{keyDir}')")
    bckp_parser.add_argument('--period', type=int, default=5, help="backup period")          
    bckp_parser.add_argument('--delete', type=int, default=3, help="how many files should be kept in Level 4")
    bckp_parser.add_argument('--test', action='store_true', help="to test behaviour every call generates a timestamp with a new day")
    bckp_parser.set_defaults(func=backup_handling)

    rest_parser = subparsers.add_parser("restore", help="restore stuff")
    rest_parser.add_argument('src', help="path to the source file")              
    rest_parser.add_argument('email', help="keyname,... email in most cases")         
    rest_parser.add_argument('--dst', default=os.path.join(homeDir, "restored.txt"), help=f"path to the destination folder (default: {os.path.join(homeDir, 'restored.txt')})")           #a dir
    rest_parser.add_argument('--path', default=keyDir, help=f"where is the key stored (default: '{keyDir}')")
    rest_parser.set_defaults(func=restore_handling)

    args = main_parser.parse_args()
    #logging.info(args) #      !!!!!   will put the passphrase in the log    !!!!!
    args.func(args)
        
        