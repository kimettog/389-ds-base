# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2016 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---
#
import logging

import pytest
from lib389.tasks import *
from lib389.topologies import topology_st

from lib389._constants import (defaultProperties, DEFAULT_SUFFIX, ReplicaRole,
                               REPLICAID_MASTER_1, REPLICATION_BIND_DN, REPLICATION_BIND_PW,
                               REPLICATION_BIND_METHOD, REPLICATION_TRANSPORT, RA_NAME,
                               RA_BINDDN, RA_BINDPW, RA_METHOD, RA_TRANSPORT_PROT)

log = logging.getLogger(__name__)


def test_ticket47781(topology_st):
    """
        Testing for a deadlock after doing an online import of an LDIF with
        replication data.  The replication agreement should be invalid.
    """

    log.info('Testing Ticket 47781 - Testing for deadlock after importing LDIF with replication data')

    #
    # Setup Replication
    #
    log.info('Setting up replication...')
    topology_st.standalone.replica.enableReplication(suffix=DEFAULT_SUFFIX, role=ReplicaRole.MASTER,
                                                     replicaId=REPLICAID_MASTER_1)

    properties = {RA_NAME: r'meTo_$host:$port',
                  RA_BINDDN: defaultProperties[REPLICATION_BIND_DN],
                  RA_BINDPW: defaultProperties[REPLICATION_BIND_PW],
                  RA_METHOD: defaultProperties[REPLICATION_BIND_METHOD],
                  RA_TRANSPORT_PROT: defaultProperties[REPLICATION_TRANSPORT]}
    # The agreement should point to a server that does NOT exist (invalid port)
    repl_agreement = topology_st.standalone.agreement.create(suffix=DEFAULT_SUFFIX,
                                                             host=topology_st.standalone.host,
                                                             port=5555,
                                                             properties=properties)

    #
    # add two entries
    #
    log.info('Adding two entries...')
    try:
        topology_st.standalone.add_s(Entry(('cn=entry1,dc=example,dc=com', {
            'objectclass': 'top person'.split(),
            'sn': 'user',
            'cn': 'entry1'})))
    except ldap.LDAPError as e:
        log.error('Failed to add entry 1: ' + e.message['desc'])
        assert False

    try:
        topology_st.standalone.add_s(Entry(('cn=entry2,dc=example,dc=com', {
            'objectclass': 'top person'.split(),
            'sn': 'user',
            'cn': 'entry2'})))
    except ldap.LDAPError as e:
        log.error('Failed to add entry 2: ' + e.message['desc'])
        assert False

    #
    # export the replication ldif
    #
    log.info('Exporting replication ldif...')
    args = {EXPORT_REPL_INFO: True}
    exportTask = Tasks(topology_st.standalone)
    try:
        exportTask.exportLDIF(DEFAULT_SUFFIX, None, "/tmp/export.ldif", args)
    except ValueError:
        assert False

    #
    # Restart the server
    #
    log.info('Restarting server...')
    topology_st.standalone.stop()
    topology_st.standalone.start()

    #
    # Import the ldif
    #
    log.info('Import replication LDIF file...')
    importTask = Tasks(topology_st.standalone)
    args = {TASK_WAIT: True}
    try:
        importTask.importLDIF(DEFAULT_SUFFIX, None, "/tmp/export.ldif", args)
        os.remove("/tmp/export.ldif")
    except ValueError:
        os.remove("/tmp/export.ldif")
        assert False

    #
    # Search for tombstones - we should not hang/timeout
    #
    log.info('Search for tombstone entries(should find one and not hang)...')
    topology_st.standalone.set_option(ldap.OPT_NETWORK_TIMEOUT, 5)
    topology_st.standalone.set_option(ldap.OPT_TIMEOUT, 5)
    try:
        entries = topology_st.standalone.search_s(DEFAULT_SUFFIX, ldap.SCOPE_SUBTREE, 'objectclass=nsTombstone')
        if not entries:
            log.fatal('Search failed to find any entries.')
            assert PR_False
    except ldap.LDAPError as e:
        log.fatal('Search failed: ' + e.message['desc'])
        assert PR_False


if __name__ == '__main__':
    # Run isolated
    # -s for DEBUG mode
    CURRENT_FILE = os.path.realpath(__file__)
    pytest.main("-s %s" % CURRENT_FILE)
