import json
import boto3
import logging
import csv
import io
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional

sts_client = boto3.client("sts")
account_id = sts_client.get_caller_identity()["Account"]
qs_client = boto3.client('quicksight')
lambda_aws_region = os.environ['AWS_REGION']
print(lambda_aws_region)
aws_region = 'us-east-1'
ssm = boto3.client('ssm', region_name=lambda_aws_region)

def get_ssm_parameters(ssm_string):
    config_str = ssm.get_parameter(
        Name=ssm_string
    )['Parameter']['Value']
    return json.loads(config_str)

def get_s3_info(account_id, lambda_aws_region):
    bucket_name = get_ssm_parameters('/qs/config/groups')
    bucket_name = bucket_name['bucket-name']
    return bucket_name


def lambda_handler(event, context):
    sts_client = boto3.client("sts", region_name=aws_region)
    account_id = sts_client.get_caller_identity()["Account"]

    # call s3 bucket
    s3 = boto3.resource('s3')
    bucketname = get_s3_info(account_id, lambda_aws_region)
    bucket = s3.Bucket(bucketname)

    key = 'monitoring/quicksight/group_membership/group_membership.csv'
    key2 = 'monitoring/quicksight/object_access/object_access.csv'
    tmpdir = tempfile.mkdtemp()
    local_file_name = 'group_membership.csv'
    local_file_name2 = 'object_access.csv'
    path = os.path.join(tmpdir, local_file_name)
    print(path)

    lists = []
    access = []
    groups = list_groups(account_id, aws_region)
    for group in groups:
        members = list_group_memberships(group['GroupName'], account_id, aws_region)
        for member in members:
            lists.append([group['GroupName'], member['MemberName']])

    print(len(lists))
    print(lists)

    with open(path, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        for line in lists:
            writer.writerow(line)
    bucket.upload_file(path, key)

    path = os.path.join(tmpdir, local_file_name2)
    print(path)
    dashboards = list_dashboards(account_id, lambda_aws_region)

    for dashboard in dashboards:
        dashboardid = dashboard['DashboardId']

        response = describe_dashboard_permissions(account_id, dashboardid, lambda_aws_region)
        permissions = response['Permissions']
        for principal in permissions:
            principal = principal['Principal'].split("/")
            ptype = principal[0].split(":")
            ptype = ptype[-1]
            additional_info = principal[-2]
            principal = principal[-1]

            access.append(['dashboard', dashboard['Name'], ptype, principal, additional_info])

    datasets = list_datasets(account_id, lambda_aws_region)

    for dataset in datasets:
        if dataset['Name'] not in ['Business Review', 'People Overview', 'Sales Pipeline',
                                   'Web and Social Media Analytics']:
            datasetid = dataset['DataSetId']

            response = describe_data_set_permissions(account_id, datasetid, lambda_aws_region)
            permissions = response['Permissions']
            for principal in permissions:
                principal = principal['Principal'].split("/")
                ptype = principal[0].split(":")
                ptype = ptype[-1]
                additional_info = principal[-2]
                principal = principal[-1]

                access.append(['dataset', dataset['Name'], ptype, principal, additional_info])

    print(access)
    with open(path, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        for line in access:
            writer.writerow(line)

    # upload file from tmp to s3 key

    bucket.upload_file(path, key2)


def list_group_memberships(
        group_name: str,
        account_id: str,
        aws_region: str,
        namespace: str = "gademo"
) -> List[Dict[str, Any]]:
    return _list(
        func_name="list_group_memberships",
        attr_name="GroupMemberList",
        account_id=account_id,
        GroupName=group_name,
        Namespace=namespace,
        aws_region=aws_region
    )


def list_users(account_id, aws_region) -> List[Dict[str, Any]]:
    return _list(
        func_name="list_users",
        attr_name="UserList",
        Namespace='gademo',
        account_id=account_id,
        aws_region=aws_region
    )


def _list(
        func_name: str,
        attr_name: str,
        account_id: str,
        aws_region: str,
        **kwargs, ) -> List[Dict[str, Any]]:
    qs_client = boto3.client('quicksight', region_name=aws_region)
    func: Callable = getattr(qs_client, func_name)
    response = func(AwsAccountId=account_id, **kwargs)
    next_token: str = response.get("NextToken", None)
    result: List[Dict[str, Any]] = response[attr_name]
    while next_token is not None:
        response = func(AwsAccountId=account_id, NextToken=next_token, **kwargs)
        next_token = response.get("NextToken", None)
        result += response[attr_name]
    return result


def list_groups(
        account_id, aws_region
) -> List[Dict[str, Any]]:
    return _list(
        func_name="list_groups",
        attr_name="GroupList",
        Namespace='gademo',
        account_id=account_id,
        aws_region=aws_region
    )


def list_dashboards(
        account_id,
        aws_region
) -> List[Dict[str, Any]]:
    return _list(
        func_name="list_dashboards",
        attr_name="DashboardSummaryList",
        account_id=account_id,
        aws_region=aws_region
    )


def describe_dashboard_permissions(account_id, dashboardid, aws_region):
    qs_client = boto3.client('quicksight', region_name=aws_region)
    res = qs_client.describe_dashboard_permissions(
        AwsAccountId=account_id,
        DashboardId=dashboardid
    )
    return res


def list_datasets(
        account_id,
        aws_region
) -> List[Dict[str, Any]]:
    return _list(
        func_name="list_data_sets",
        attr_name="DataSetSummaries",
        account_id=account_id,
        aws_region=aws_region
    )


def describe_data_set_permissions(account_id, datasetid, aws_region):
    qs_client = boto3.client('quicksight', region_name=aws_region)
    res = qs_client.describe_data_set_permissions(
        AwsAccountId=account_id,
        DataSetId=datasetid
    )
    return res
