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

from pprint import pprint
from pathlib import Path
from datetime import datetime as dt, timedelta

KEYLEN = 4096
periodUnits = {"level_2":"days", "level_3":"weeks", "level_4":"months"}  # possible: microseconds, milliseconds, seconds, minutes, hours, days, weeks, months, years
backupLevels = ("level_1", "level_2", "level_3", "level_4")
backupDirs = dict() #to store the directorys for the various backup levels
youngsters = dict() #to store the newest file for the various levels

#-----------------------------------------------------------------------------------------------------------
#--------------------------------------------------key stuf-------------------------------------------------
#-----------------------------------------------------------------------------------------------------------

def generateKey(email, passphrase, path, clean=False):
    if clean: os.system(f'rm -rf {path}/*')
    gpg = gnupg.GPG(homedir=args.path)
    #default is RSA
    input_data = gpg.gen_key_input(
        key_length = KEYLEN,
        expire_date = 0,
        name_email=email,
        passphrase=passphrase)
    key = gpg.gen_key(input_data)
    print (f'Key generated fingerprint: {key.fingerprint}')
    print('Output:')
    pprint(key.stderr)
    return key

def add_key(args):
    print("-------------Before key generation--------------------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")
    genKey = generateKey(args.email, args.passphrase, args.path, True)
    print("--------------After key generation-----------------list-keys----------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    print("--------------After key generation-----------------list-secret-keys---")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")

    export_key(args)
    
    print(f"list-keys fingerprint:{genKey.fingerprint}--------")
    os.system(f"gpg2 --homedir {args.path} --list-keys {genKey.fingerprint}")
    print(f"list-secret-keys fingerprint:{genKey.fingerprint}")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys {genKey.fingerprint}")


def export_key(args):
    print("-------------Before key removal--------------------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")
    print("---------export and delete secret keys--------------------------------")
    os.system(f"gpg2 -a --homedir {args.path} --batch --pinentry-mode loopback --passphrase {args.passphrase} --export-secret-keys {args.email} > priv_key.asc")
    #os.system(f"gpg2 --homedir {args.path} --batch --pinentry-mode loopback --passphrase {args.passphrase} --export-secret-keys {genKey.fingerprint} > priv_key.bin")
    os.system(f"gpg2 --homedir {args.path} --batch --pinentry-mode loopback --yes --passphrase {args.passphrase} --delete-secret-keys {args.email}")
    print(f"private key exported to '{os.path.dirname(args.argv[0])}\\priv_key.asc'")
    print("...\n...\n...")
    print("---------------After key removal-------------------list-keys----------")
    os.system(f"gpg2 --homedir {args.path} --list-keys")
    print("---------------After key removal-------------------list-secret-keys---")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")


def remove_key(args):
    gpg = gnupg.GPG(homedir=args.path)
    remove_result = gpg.delete_keys(args.email)
    pprint(str(remove_result))
    

def import_key(args):
    gpg = gnupg.GPG(homedir=args.path)
    #gpg.encoding = 'utf-8'
    key_data = open(args.keyfile, 'rb').read()
    import_result = gpg.import_keys(key_data)
    pprint("-------------------------------------------------------------------------------------------")
    pprint("Attention: propably the secret private key is now also in the keyring on the local machine!")
    pprint(f"Check output of command: 'gpg2 --homedir {args.path} --list-secret-keys'")
    pprint("-------------------------------------------------------------------------------------------")
    os.system(f"gpg2 --homedir {args.path} --list-secret-keys")

    pprint(import_result.results)
    return import_result


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
        file_ts = dt.strptime(file.split("_")[0], "%Y%m%d%H%M%S")
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
        youngster_ts = dt.strptime(string_ts, "%Y%m%d%H%M%S")
        youngsters[level] = (youngster, youngster_ts)
        logging.info(f"Youngest file in '{backupDirs[level]}': '{youngster}'")


def doInitialSetup(cryptedFile):
    if(not any(os.scandir(backupDirs["level_4"]))):
        shutil.move(cryptedFile, backupDirs["level_4"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_4']}'")
        return False
    elif(not any(os.scandir(backupDirs["level_3"]))):
        shutil.move(cryptedFile, backupDirs["level_3"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_3']}'")
        return False
    elif(not any(os.scandir(backupDirs["level_2"]))):
        shutil.move(cryptedFile, backupDirs["level_2"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_2']}'")
        return False
    elif(not any(os.scandir(backupDirs["level_1"]))):
        shutil.move(cryptedFile, backupDirs["level_1"])
        logging.info(f"Initial Setup: '{cryptedFile}' moved to '{backupDirs['level_1']}'")
        return False
    else:
        logging.info("Initial Setup already done.")
        return True


def encryptFile(file, keyName, homedir, testmode):
    outputPath, fileName = os.path.split(file)
    if(testmode):
        l1_youngster = dt.strptime(sorted(os.listdir(backupDirs["level_1"]))[-1].split("_")[0], "%Y%m%d%H%M%S")
        ts = (l1_youngster + timedelta(days=1)).strftime("%Y%m%d%H%M%S")
    else:
        ts = dt.now().strftime("%Y%m%d%H%M%S")
    
    outputFile = os.path.join(outputPath, f"{ts}_{fileName}.gpg")
    status = os.system(f"gpg2 --homedir {homedir} -o {outputFile} -e -r {keyName} {file}")
    if(status==0):
        logging.info(f"File '{file}' encrypted with key '{keyName}' from '{homedir}' -> '{outputFile}'")
    else:
        logging.info (f"encryption status: nok; exit code = '{status}'")

    return outputFile


def checkDestination(destPath):
    for level in backupLevels:
        backupDirs[level] = os.path.join(destPath, level)

        if(not os.path.isdir(backupDirs[level])):
            os.makedirs(backupDirs[level])
        logging.info(f"'{level}' dir: '{backupDirs[level]}'")


def backup_handling(args):
    #new concept
    #vier Ordner L1(Tagesbackups), L2(älter als x Tage), L3(älter als x Wochen) und L4(älter als x Monate)
    #Kopiere src in L1 als src_<dt>
    #wenn Ordner im nächsten Level leer, schiebe File dorthin (wiederhole bis zum letzten Level)
    #wenn File in level_x um x (days, weeks, months,.. je nach level) älter als jüngstes File im nächsten Level level_x+1, schiebe File dorthin
    #wenn File in nächstes Level geschoben, lösche im aktuellen Level alle Files die älter sind als jüngstes File im nächsten Level vor dem Verschieben
    
    checkDestination(args.dst)
    tmpFile = shutil.copy(args.src, args.dst) #just copy the file in the root to encrypt and move it afterwards
    cryptedFile = encryptFile(tmpFile, args.email, args.path, args.test)
    os.remove(tmpFile)

    if(doInitialSetup(cryptedFile) == False):
        exit()
    else:
        shutil.move(cryptedFile, backupDirs["level_1"])
    
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


if __name__ == '__main__':
    if platform.system() != 'Linux':
        print (f'Platform {platform.system()} not suported.')
        exit()
    
    appPath = os.path.dirname(sys.argv[0])
    logFile = os.path.join(appPath, "cryptbackup.log")
    logging.basicConfig(filename=logFile,level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%d.%m.%Y %H:%M:%S')
    logging.info("-------------------------------------------------------Start new backup run-------------------------------------------------------")

    homepath = Path.home().as_posix() + "/.gnupg"

    main_parser = argparse.ArgumentParser(description="A tool to do encrypted backups of a single file.")
    subparsers = main_parser.add_subparsers(title="subcommands", dest="sub_func", required=True, description="type subcommand -h to get help", help="additional help")

    addkey_parser = subparsers.add_parser("add_key", help="generate key and export the secret key")
    addkey_parser.add_argument('--path', default=homepath, help=f"where should the key get stored (default: {homepath})")
    addkey_parser.add_argument('email', help="user name")
    addkey_parser.add_argument('passphrase', help="passphrase")
    addkey_parser.set_defaults(func=add_key)
  
    remkey_parser = subparsers.add_parser("remove_key", help="remove key")
    remkey_parser.add_argument('--path', default=homepath, help=f"where is the key to remove stored (default: {homepath})")
    remkey_parser.add_argument('email', help="user name")
    remkey_parser.set_defaults(func=remove_key)

    impkey_parser = subparsers.add_parser("import_key", help="import key")
    impkey_parser.add_argument('--path', default=homepath, help=f"where is the keyring the key should get imported to (default: {homepath})")
    impkey_parser.add_argument('keyfile', help="the keyfile to import")
    impkey_parser.set_defaults(func=import_key)

    expkey_parser = subparsers.add_parser("export_key", help="export key and just keep the public key")
    expkey_parser.add_argument('--path', default=homepath, help=f"where is the keyring the key should get imported to (default: {homepath})")
    expkey_parser.add_argument('email', help="the key to export")
    expkey_parser.add_argument('passphrase', help="passphrase")
    expkey_parser.set_defaults(func=export_key)

    bckp_parser = subparsers.add_parser("backup", help="backup stuff")
    bckp_parser.add_argument('src', help="path to the source file")              
    bckp_parser.add_argument('dst', help="path to the destination folder")           #a dir
    bckp_parser.add_argument('email', help="user name for encrytion")          #email in most cases
    bckp_parser.add_argument('--path', default=homepath, help=f"where is the key stored (default: {homepath})")
    bckp_parser.add_argument('--period', type=int, default=5, help="backup period")          
    bckp_parser.add_argument('--delete', type=int, default=5, help="how many files should be kept in Level 4")
    bckp_parser.add_argument('--test', action='store_true', help="to test behaviour every call generates a timestamp with a new day")
    bckp_parser.set_defaults(func=backup_handling)

    rest_parser = subparsers.add_parser("restore", help="restore stuff")
    rest_parser.add_argument('src', help="path to the source file")              #a file
    rest_parser.add_argument('email', help="user name for encrytion")          #email in most cases
    rest_parser.add_argument('--dst', default=os.path.join(appPath, "restored.txt"), help=f"path to the destination folder (default: {os.path.join(appPath, 'restored.txt')})")           #a dir
    rest_parser.add_argument('--path', default=homepath, help=f"where is the key stored (default: {homepath})")
    rest_parser.set_defaults(func=restore_handling)

    args = main_parser.parse_args()
    logging.info(args)
    args.func(args)
        
        