import graphviz
import boto3
import re
import logging
from pprint import pprint
import argparse

'''
AWS credentials need to be set roughly like the following:
[PROFILENAME] #ACC-ID
role_arn = arn:aws:iam::ACC-ID:role/ROLENAME
source_profile = OTHER-KEY
region = ap-southeast-2
'''

# [ltail=cluster_0 lhead=cluster_2];

def getCredentialsList():  # TODO make generic
    CRED_FILE_LOCATION = 'C:\\Users\\Tully\\.aws\\credentials'
    p = re.compile('\[\w+\]\ \#\d+')
    with open(CRED_FILE_LOCATION, 'r') as myfile:
        result_arr = []
        for name in p.findall(myfile.read()):
            temp_arr = name.replace('[', '').replace(']', '').split(' #')
            result_arr.append({'name': temp_arr[0], 'id': temp_arr[1]})
        return result_arr


def main(args):
    # Set-up Logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.info(args)
    logger.info(args.accounts)
    logger.info(args.region)
    acc_list = []
    for acc in getCredentialsList():
        for search_term in args.accounts:
            # logger.info("Searching for: '"+search_term+"' in: '"+acc['name']+"'")
            if (acc['name'].find(search_term) != -1):
                acc_list.append(acc)

    temp_peer_arr = []

    logger.info(acc_list)

    g = graphviz.Digraph('cluster_G', filename='cluster.gv')
    # NOTE: the subgraph name needs to begin with 'cluster' (all lowercase)
    #       so that Graphviz recognizes it as a special cluster subgraph

    g.attr(overlap='scale')
    ###
    # Account Sub-Graphs
    ###
    for acc in acc_list:
        logger.info(acc)
        acc_links_arr = []
        with g.subgraph(name='cluster_'+acc['id']) as acc_g:
            accname_label = '{} ({})'.format(acc['name'], acc['id'])
            # Graph attributes
            acc_g.attr(label=accname_label, color='black')

            session = boto3.Session(profile_name=acc['name'],
                                    region_name=args.region)
            iam = session.resource('iam')
            ###
            # Role Sub-Graphs
            ###
            with acc_g.subgraph(name='cluster_'+acc['id']+'_roles') as roles_g:
                for role in iam.roles.all(): # TODO add check and node for no roles
                    roles_g.node(role.name)
                    if role.policies is not None:
                        for role_policy in role.policies.all():
                            # print(role_policy.policy_document)
                            pprint(role_policy.policy_document)
                    # # if role.attached_policies is not None:
                    #     for attached_policy in role.attached_policies:
                    #         print(attached_policy.default_version)

    g.render(filename='out/IAM_'+str(args.accounts)+'.gv', view=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Creates DOT graphs of AWS resources using Graphviz")
    parser.add_argument('--accounts', type=str, nargs='+', help="Accounts to check using profiles from the ~/.aws/credentials file", required=True)
    args = parser.parse_args()

    main(args)
