#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from os import environ
from sys import argv, exit, modules
import signal
import boto3
import pandas as pd
from botocore.exceptions import ClientError, ProfileNotFound

'''
+------------------------------------------------------------------------
+
+ For each AWS Region, enumerate and count various resource instances
+
+ User has option of specifying specific Meta Region e.g. US
+
+  Expects "aws configure" to have been run and AWS_PROFILE to have
+  been previously set e.g:
+
+       export AWS_PROFILE=<profile_name>
+
+ Dependencies:
+
+       Python Panda module
+       Python Boto3 and botocore modules
+
+------------------------------------------------------------------------

================================ DISCLAIMER ====================================
There are inherent dangers in the use of any software, we caution you to make
sure you completely understand the potential risks before using this software.

This Software is provided "as is" without warranty of any kind, either express
or implied. Use at your own risk.

The use of this software is done at your own discretion and risk and with agreement
that you will be solely responsible for any damage to your computer system or
loss of data that results from such activities. You are solely responsible for
adequate protection and backup of the data and equipment used in connection with
this software, and we will not be liable for any damages that you may suffer in
connection with using, modifying or distributing any of this software. No advice
or information, whether oral or written shall create any warranty for the software.

We make make no warranty that:

- this software will meet your requirements
- the results obtained from this software will be effective, accurate or reliable
- any errors in this software will be corrected

In no event shall we be liable to you or any third parties for any special,
punitive, incidental, indirect or consequential damages of any kind, or any
damages whatsoever, including, without limitation, those resulting from loss of
use, data or profits, and on any theory of liability, arising out of or in
connection with the use of this software.
=============================== END DISCLAIMER =================================
'''

__author__ = "Michael E. OConnor, Lacework, Inc."

# this is a pointer to the module object instance itself.
this = modules[__name__]

# Define Global File Object Variable
this.fo = None

# Using Panda, format AWS Instance JSON into human readable data frames

def get_ec2_status(response):
    ''' EC2 Instances '''
    av_zones, inst_ids, state_names = [], [], []
    for res in response['Reservations']:
        for ins in res['Instances']:
            av_zones.append(ins['Placement']['AvailabilityZone'])
            inst_ids.append(ins['InstanceId'])
            state_names.append(ins['State']['Name'])

    return pd.DataFrame({
        'InstanceId': inst_ids,
        'AZ': av_zones,
        'State': state_names
    })

def get_nat_status(response):
    ''' NAT Instances '''
    nat_ids, nat_states, vpc_ids = [], [], []
    for nat in response['NatGateways']:
        nat_ids.append(nat['NatGatewayId'])
        nat_states.append(nat['State'])
        vpc_ids.append(nat['VpcId'])

    return pd.DataFrame({
        'NatgatewayId': nat_ids,
        'State': nat_states,
        'VpcId': vpc_ids
    })

def get_elbv1_status(response):
    ''' ELB v1 '''
    elb_name, elb_scheme, elb_target = [], [], []
    for elbs in response['LoadBalancerDescriptions']:
        elb_name.append(elbs['LoadBalancerName'])
        elb_scheme.append(elbs['Scheme'])
        elb_target.append(elbs['HealthCheck']['Target'])

    return pd.DataFrame({
        'ELB Name': elb_name,
        'Scheme': elb_scheme,
        'Health Target': elb_target
    })

def get_elbv2_status(response):
    ''' ELB v2 '''
    elb_name, elb_scheme, elb_type = [], [], []
    for elbs in response['LoadBalancers']:
        elb_name.append(elbs['LoadBalancerName'])
        elb_scheme.append(elbs['Scheme'])
        elb_type.append(elbs['Type'])

    return pd.DataFrame({
        'ELB Name': elb_name,
        'Scheme': elb_scheme,
        'Type': elb_type
    })

def get_rds_status(response):
    ''' RDS instances '''
    dbs_id, dbs_pgroup, dbs_status = [], [], []
    for dbs in response['DBClusters']:
        dbs_id.append(dbs['DBClusterIdentifier'])
        dbs_pgroup.append(dbs['DBClusterParameterGroup'])
        dbs_status.append(dbs['Status'])

    return pd.DataFrame({
        'Identifyer': dbs_id,
        'Param Group': dbs_pgroup,
        'Status': dbs_status
    })

def get_redshift_status(response):
    ''' Redshift Clusters '''
    rs_name, rs_azone, rs_nodes = [], [], []
    for dbs in response['Clusters']:
        rs_name.append(dbs['DBName'])
        rs_azone.append(dbs['AvailabilityZone'])
        rs_nodes.append(dbs['NumberOfNodes'])

    return pd.DataFrame({
        'Identifyer': rs_name,
        'AZ': rs_azone,
        'Node Count': rs_nodes
    })

# Cycle through all available AWS Regions enumerating applicable resources

def main():
    ''' Main Body '''
    try:
        profile = environ['AWS_PROFILE']
        resp = input('AWS_PROFILE = [{}]. Press enter to confirm '
                     'or specify new: '.format(profile))
        if bool(resp.strip()):
            profile = resp
    except KeyError:
        profile = input('Please enter AWS Profile: ')

    total_resource_cnt = 0
    valid_areas = ['all', 'us', 'ap', 'ca', 'eu', 'sa']
    area = valid_areas[0]
    ec2 = boto3.client('ec2')
    outputFile = profile + '_AWS_Resources.txt'

    print('Using AWS Credentials associated with Profile = ' + profile)

    try:
        session = boto3.session.Session(profile_name=profile)
    except ProfileNotFound as e:
        print(e)
        exit(1)

    # Generate a list of all available AWS regions

    ec2_regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]

    print('Found {} Total AWS Regions'.format(len(ec2_regions)))

    # Check for Meta Geographic Region provided as command line argument

    if len(argv) == 2:
        area = argv[1].lower()
        if area in valid_areas:
            print('Filtering on {} Regions'.format(area.upper()))
        else:
            print('Sorry, can only filter on one of the following: {}'.format(valid_areas))
            exit(1)

    this.fo = open(outputFile, "w")
    this.fo.write('Listing AWS Resource Detail associated with AWS_Profile = ' + profile)
    this.fo.write('\nFiltering on Regions: ' + area.upper())


    for reg in ec2_regions:

        # If filtering only on one specific geographic region, skip if no match

        if area != valid_areas[0] and not reg.startswith(area):
            continue

        # At this point, scanning all regions or we have a match

        print('\nScanning AWS Region: {:^14}'.format(reg.upper()))

        # Check for EC2 instances

        conn = session.client('ec2', region_name=reg)
        try:
            response = conn.describe_instances()
        except ClientError as e:
            fatal(e)
        ec2_df = get_ec2_status(response)
        ec2_cnt = len(ec2_df.index)
        print('{:3} EC2 Instances'.format(ec2_cnt))
        if ec2_cnt:
            this.fo.write('\n\n*** {:3} EC2 Instances found in: {} ***\n\n'.format(ec2_cnt, reg.upper()))
            this.fo.write(str(ec2_df))
        total_resource_cnt += ec2_cnt

        # Check for NAT instances

        try:
            response = conn.describe_nat_gateways()
        except ClientError as e:
            fatal(e)
        nat_df = get_nat_status(response)
        nat_cnt = len(nat_df.index)
        print('{:3} NAT Instances'.format(nat_cnt))
        if nat_cnt:
            this.fo.write('\n\n*** {:3} NAT Instances found in: {} ***\n\n'.format(nat_cnt, reg.upper()))
            this.fo.write(str(nat_df))
        total_resource_cnt += nat_cnt

        # Check for ELB v1 Instances

        conn = session.client('elb', region_name=reg)
        try:
            response = conn.describe_load_balancers()
        except ClientError as e:
            fatal(e)
        elb_df = get_elbv1_status(response)
        elb_cnt = len(elb_df.index)
        print('{:3} v1 ELBs'.format(elb_cnt))
        if elb_cnt:
            this.fo.write('\n\n*** {:3} v1 ELBs found in: {} ***\n\n'.format(elb_cnt, reg.upper()))
            this.fo.write(str(elb_df))
        total_resource_cnt += elb_cnt

        # Check for ELB v2 Instances

        conn = session.client('elbv2', region_name=reg)
        try:
            response = conn.describe_load_balancers()
        except ClientError as e:
            fatal(e)

        elb_df = get_elbv2_status(response)
        elb_cnt = len(elb_df.index)
        print('{:3} v2 ELBs'.format(elb_cnt))
        if elb_cnt:
            this.fo.write('\n\n*** {:3} v2 ELBs found in: {} ***\n\n'.format(elb_cnt, reg.upper()))
            this.fo.write(str(elb_df))
        total_resource_cnt += elb_cnt

        # Check for RDS Clusters

        conn = session.client('rds', region_name=reg)
        try:
            response = conn.describe_db_clusters()
        except ClientError as e:
            fatal(e)

        rds_df = get_rds_status(response)
        rds_cnt = len(rds_df.index)
        print('{:3} RDS Clusters'.format(rds_cnt))
        if rds_cnt:
            this.fo.write('\n\n*** {:3} RDS Clusters found in: {} ***\n'.format(rds_cnt, reg.upper()))
            this.fo.write(str(rds_df))
        total_resource_cnt += rds_cnt

        # Check for Redshift Clusters

        conn = session.client('redshift', region_name=reg)
        try:
            response = conn.describe_clusters()
        except ClientError as e:
            fatal(e)
        rs_df = get_redshift_status(response)
        rs_cnt = len(rs_df.index)
        print('{:3} Redshift Clusters'.format(rs_cnt))
        if rs_cnt:
            this.fo.write('\n\n*** {:3} Redshift Clusters found in: {} ***\n'.format(rs_cnt, reg.upper()))
            this.fo.write(str(rs_df))
        total_resource_cnt += rs_cnt

    this.fo.close()
    print('\nTotal Resource Instances Found: {}'.format(total_resource_cnt))
    print('See {} for details'.format(outputFile))

def fatal(error):
    ''' Exit gracefully '''
    print(error)
    this.fo.close()
    exit(1)

def signal_handler(code, frame):
    ''' Handle CTRL-C '''
    fatal('\nSignal: {}, Program terminated by user'.format(code))

# Used when called from OS shell as script

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
