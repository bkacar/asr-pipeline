"""
    Tools for interfacing with Amazon Web Services S3 storage.
    These methods are optional, and can be enabled using --enable_aws
    at the command line when running the ASR pipeline.
"""

import boto
import boto.ec2
import boto.s3
from boto.s3.connection import S3Connection
import sys, time


def aws_update_status(message, S3_BUCKET, S3_KEYBASE):
    if S3_BUCKET == None:
        print "\n. Error, you haven't defined an S3 bucket."
        exit()
    if S3_KEYBASE == None:
        print "\n. Error, you haven't defined an S3 key base."
        exit()
                
    """Update the status field in AWS S3 for this job"""
    #s3 = boto.connect_s3()
    s3 = S3Connection()
    
    bucket = s3.lookup(S3_BUCKET)
    if bucket == None:
        s3.create_bucket(S3_BUCKET)
        bucket = s3.get_bucket(S3_BUCKET)
        
#     allBuckets = s3.get_all_buckets()
#     for bucket in allBuckets:
#         print(str(bucket.name))
#         allKeys = bucket.get_all_keys()
#         for key in allKeys:
#             print "\t", key.name
    
    STATUS_KEY = S3_KEYBASE + "/status"
    print "attempting to get key", STATUS_KEY
    key = bucket.get_key(STATUS_KEY)
    if key == None:
        key = bucket.new_key(STATUS_KEY)
        #key = bucket.get_key(STATUS_KEY) 
    if key == None:
        print "\n. Error 39 - the key is None"
        exit()   
    key.set_contents_from_string(message)
    
    print "\n. S3 Status Update:", key.get_contents_as_string()


def push_database_to_s3(dbpath, S3_BUCKET, S3_KEYBASE):
    """Pushes the startup files for a job to S3.
        jobid is the ID of the Job object,
        filepath is the path on this server to the file."""
    #s3 = S3Connection()
    
    s3 = S3Connection()
    
    #s3 = boto.connect_s3()
    #print "46: connected to", s3.Location
    
#     allBuckets = s3.get_all_buckets()
#     for bucket in allBuckets:
#         print(str(bucket.name))
#         allKeys = bucket.get_all_keys()
#         for key in allKeys:
#             print "\t", key.name
    
    bucket = s3.lookup(S3_BUCKET)
    if bucket == None:
        bucket = s3.create_bucket(S3_BUCKET)
        bucket = s3.get_bucket(S3_BUCKET)
    
    
    SQLDB_KEY = S3_KEYBASE + "/sqldb"
    key = bucket.get_key(SQLDB_KEY)
    if key == None:
        key = bucket.new_key(SQLDB_KEY)
    key.set_contents_from_filename(dbpath)
    
    
