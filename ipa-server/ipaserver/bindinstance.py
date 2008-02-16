# Authors: Simo Sorce <ssorce@redhat.com>
#
# Copyright (C) 2007  Red Hat
# see file 'COPYING' for use and warranty information
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; version 2 only
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#

import string
import tempfile
import shutil
import os
import socket

import service
import sysrestore
from ipa import ipautil

class BindInstance(service.Service):
    def __init__(self):
        service.Service.__init__(self, "named")
        self.fqdn = None
	self.domain = None
        self.host = None
        self.ip_address = None
        self.realm = None
        self.sub_dict = None

    def setup(self, fqdn, ip_address, realm_name, domain_name):
        self.fqdn = fqdn
        self.ip_address = ip_address
        self.realm = realm_name
        self.domain = domain_name
        self.host = domain_name[:domain_name.find(".")]

        self.__setup_sub_dict()

    def check_inst(self):
        # So far this file is always present in both RHEL5 and Fedora if all the necessary
        # bind packages are installed (RHEL5 requires also the pkg: caching-nameserver)
        if not os.path.exists('/etc/named.rfc1912.zones'):
             return False

        return True

    def create_sample_bind_zone(self):
        bind_txt = ipautil.template_file(ipautil.SHARE_DIR + "bind.zone.db.template", self.sub_dict)
        [bind_fd, bind_name] = tempfile.mkstemp(".db","sample.zone.")
        os.write(bind_fd, bind_txt)
        os.close(bind_fd)
        print "Sample zone file for bind has been created in "+bind_name

    def create_instance(self):

        try:
            self.stop()
        except:
            pass

        self.__setup_zone()
        self.__setup_named_conf()

        try:
            self.backup_state("running", self.is_running())
            self.start()
        except:
            print "named service failed to start"

    def __setup_sub_dict(self):
        self.sub_dict = dict(FQDN=self.fqdn,
                             IP=self.ip_address,
                             DOMAIN=self.domain,
                             HOST=self.host,
                             REALM=self.realm)

    def __setup_zone(self):
        self.backup_state("domain", self.domain)
        zone_txt = ipautil.template_file(ipautil.SHARE_DIR + "bind.zone.db.template", self.sub_dict)
        sysrestore.backup_file('/var/named/'+self.domain+'.zone.db')
        zone_fd = open('/var/named/'+self.domain+'.zone.db', 'w')
        zone_fd.write(zone_txt)
        zone_fd.close()

    def __setup_named_conf(self):
        sysrestore.backup_file('/etc/named.conf')
        named_txt = ipautil.template_file(ipautil.SHARE_DIR + "bind.named.conf.template", self.sub_dict)
        named_fd = open('/etc/named.conf', 'w')
        named_fd.seek(0)
        named_fd.truncate(0)
        named_fd.write(named_txt)
        named_fd.close()

        sysrestore.backup_file('/etc/resolve.conf')
        resolve_txt = "search "+self.domain+"\nnameserver "+self.ip_address+"\n"
        resolve_fd = open('/etc/resolve.conf', 'w')
        resolve_fd.seek(0)
        resolve_fd.truncate(0)
        resolve_fd.write(resolve_txt)
        resolve_fd.close()

    def uninstall(self):
        running = self.restore_state("running")
        domain = self.restore_state("domain")

        if not running is None:
            self.stop()

        if not domain is None:
            sysrestore.restore_file(os.path.join ("/var/named/", domain + ".zone.db"))

        sysrestore.restore_file('/etc/named.conf')
        sysrestore.restore_file('/etc/resolve.conf')

        if not running is None and running:
            self.start()
