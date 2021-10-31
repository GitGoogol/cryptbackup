# cryptbackup
tool to support key handling and do encrypted backups of a single file
 
 python3 must be installed
 GnuPG must be installed
 the python package gnupg is currently still needed (pip3 install gnupg), but i want to get rid of it because it did not work 100% for me
 
before using the backup function a key has to be added if not yet available
use the -h parameter to get help and see how it shoud be called

* keep backuped files less frequent as they get older
* the backup process creates 4 folders (level_1, level_2, level_3, level_4)
* every transition to the next level folder represents a different time period (default: l1->l2=days, l2->l3=weeks, l3->4=months), but can be changed in the code
* on every call of the backup command the file to backup gets encrypted and moved to l1 folder
* the default period is 5 but can be changed as a parameter setting with the backup command
* the backup process works like this (with defautl parameter period=5, delete=5):

    Initial procedure
    
        encrypted file gets moved to l1-folder
        if l2-folder is empty, move file to l2
        if l3-folder is empty, move file to l3
        if l4-folder is empty, move file to l4
        begin Initial procedure at the next backup command call
    
    After initial procedure
    
        encrypted file gets moved to l1-folder
        if the currently moved file to l1 is more than 5 **days** older than the youngest file in l2
        {
            move file to l2
           delete all files in l1 that are older than the youngest in l2 before the move
           if the currently moved file to l2 is more than 5 **weeks** older than the youngest file in l3 
           {
               move file to l3
               delete all files in l2 that are older than the youngest in l3 before the move
               if the currently moved file to l3 is more than 5 **months** older than the youngest file in l4 
               {
                   move file to l4
                   delete all files in l3 that are older than the youngest in l4 before the move
                   if there are more files in l4 folder than the delete parameter specifies, here 5
                       delete oldest files in l4 folder so that just 5 will be left
               }
           }
        }
 
 
before calling the command with the --test option (desribed below) the command has to be called 4 times without --test to do the initial setup

to test the mechanism the backup command can be executed with a --test option, so a file will be generated that has a timestamp 1 day older than the younges in l1 folder
