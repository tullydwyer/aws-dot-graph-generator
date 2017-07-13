import graphviz
import boto3
import re

'''
AWS credentials need to be set roughly like the following:
[PROFILENAME] #ACC-ID
role_arn = arn:aws:iam::ACC-ID:role/ROLENAME
source_profile = OTHER-KEY
region = ap-southeast-2
'''

REGION_TO_GRAPH = 'eu-west-1'
ACC_SEARCH_TERMS = ['PROFILENAME']
FILE_NAME = 'out/'+str(ACC_SEARCH_TERMS)+'.gv'


def getCredentialsList():  # TODO make generic
    CRED_FILE_LOCATION = 'C:\\Users\\Tully\\.aws\\credentials'
    p = re.compile('\[\w+\]\ \#\d+')
    with open(CRED_FILE_LOCATION, 'r') as myfile:
        result_arr = []
        for name in p.findall(myfile.read()):
            temp_arr = name.replace('[', '').replace(']', '').split(' #')
            result_arr.append({'name': temp_arr[0], 'id': temp_arr[1]})
        return result_arr


acc_list = []
for acc in getCredentialsList():
    for search_term in ACC_SEARCH_TERMS:
        # print("Searching for: '"+search_term+"' in: '"+acc['name']+"'")
        if (acc['name'].find(search_term) != -1):
            acc_list.append(acc)

temp_peer_arr = []

print(acc_list)

g = graphviz.Digraph('cluster_G', filename='cluster.gv')
# NOTE: the subgraph name needs to begin with 'cluster' (all lowercase)
#       so that Graphviz recognizes it as a special cluster subgraph


g.attr(overlap='scale') # , ranksep='1', nodesep='1'
for acc in acc_list:
    print(acc)
    acc_links_arr = []
    with g.subgraph(name='cluster_'+acc['id']) as acc_g:
        acc_g.attr(color='black')
        accname = '{} ({})'.format(acc['name'], acc['id'])
        acc_g.attr(label=accname)
        session = boto3.Session(profile_name=acc['name'],
                                region_name=REGION_TO_GRAPH)
        ec2 = session.resource('ec2')
        for vpc in ec2.vpcs.all():
            with acc_g.subgraph(name='cluster_'+vpc.id) as vpc_g:
                # Place IGW's
                if vpc.internet_gateways.all() is not None:
                    for igw in vpc.internet_gateways.all():
                        vpc_g.node(igw.internet_gateway_id, shape='Mdiamond')
                # Place Peering Connections's
                if vpc.requested_vpc_peering_connections.all() is not None:
                    for pcx in vpc.requested_vpc_peering_connections.all():
                        # print("Checking: "+pcx.requester_vpc.vpc_id+"  "+vpc.vpc_id)
                        print("pcx status: ", pcx.status)
                        if pcx.requester_vpc.vpc_id == vpc.vpc_id and pcx.status['Code'] == 'active':
                            vpc_g.node('r | ' + pcx.vpc_peering_connection_id, shape='tripleoctagon')
                            if pcx.id not in temp_peer_arr:
                                temp_peer_arr.append(pcx.id)
                            else:
                                g.edge('r | ' + pcx.vpc_peering_connection_id, 'a | ' + pcx.vpc_peering_connection_id, dir="both")
                if vpc.accepted_vpc_peering_connections.all() is not None:
                    for pcx in vpc.accepted_vpc_peering_connections.all():
                        # print("Checking: "+pcx.requester_vpc.vpc_id+"  "+vpc.vpc_id)
                        print("pcx status: ", pcx.status)
                        if pcx.accepter_vpc.vpc_id == vpc.vpc_id and pcx.status['Code'] == 'active':
                            vpc_g.node('a | ' + pcx.vpc_peering_connection_id, shape='tripleoctagon')
                            if pcx.id not in temp_peer_arr:
                                temp_peer_arr.append(pcx.id)
                            else:
                                g.edge('r | ' + pcx.vpc_peering_connection_id, 'a | ' + pcx.vpc_peering_connection_id, dir="both")
                vpc_name = ''
                if vpc.tags is not None:
                    for tag in vpc.tags:
                        if tag['Key'] == 'Name':
                            vpc_name = tag['Value']
                vpc_g.attr(color='black')
                vpc_g.attr(label='{} ({}) | {}'.format(vpc_name, vpc.id, vpc.cidr_block))
                for subnet in vpc.subnets.all():
                    with vpc_g.subgraph(name='cluster_'+subnet.id) as subnet_g:
                        subnet_name = ''
                        if subnet.tags is not None:
                            for tag in subnet.tags:
                                if tag['Key'] == 'Name':
                                    subnet_name = tag['Value']
                        subnet_g.attr(label='{} ({})'.format(subnet_name, subnet.id))
                        subnet_g.node(subnet.cidr_block)
                    for route_table in vpc.route_tables.all():
                        print(route_table.id)
                        for subnet_association in route_table.associations:
                            print(subnet_association.subnet_id)
                            if subnet.id == subnet_association.subnet_id:
                                for route in route_table.routes:
                                    print('{} -> {}'.format(route.destination_cidr_block, route.gateway_id))
                                    if str(route.gateway_id).startswith('igw-'):
                                        g.edge(subnet.cidr_block, route.gateway_id)
                                    if str(route.nat_gateway_id).startswith('ngw-'):
                                        vpc_g.node(route.nat_gateway_id, shape='circle')
                                        g.edge(subnet.cidr_block, route.nat_gateway_id)
                                    if str(route.egress_only_internet_gateway_id).startswith('eigw-'):
                                        vpc_g.node(route.egress_only_internet_gateway_id, shape='circle')
                                        g.edge(subnet.cidr_block, route.egress_only_internet_gateway_id)
                                    if str(route.gateway_id).startswith('vgw-'):
                                        vpc_g.node(route.gateway_id, shape='doublecircle')
                                        g.edge(subnet.cidr_block, route.gateway_id)
                                    if str(route.vpc_peering_connection_id).startswith('pcx-'):
                                        pcx = ec2.VpcPeeringConnection(route.vpc_peering_connection_id)
                                        if pcx.accepter_vpc.vpc_id == vpc.vpc_id:
                                            g.edge(subnet.cidr_block, 'a | '+route.vpc_peering_connection_id)
                                        else:
                                            g.edge(subnet.cidr_block, 'r | '+route.vpc_peering_connection_id)

g.render(filename=FILE_NAME, view=True)
