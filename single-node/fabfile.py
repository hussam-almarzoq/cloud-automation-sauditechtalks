import time

import digitalocean
import fabtools
from fabric.api import *
from fabtools import systemd

APP_DIR = "/var/www/html/"
APP_REPO = "https://github.com/chapagain/crud-php-simple"
env.user = "root"
TOKEN = "7f52a2f91cc94d196ccb0b5279d4187adc404e31c76ea12c1c57477384473f35"
manager = digitalocean.Manager(token=TOKEN)


def create_nodes(name, tag, num=1):
    names = []
    for i in range(int(num)):
        names.append(name + "-" + str(i))

    tag = digitalocean.Tag(token=TOKEN, name=tag)
    tag.create()

    droplets = digitalocean.Droplet.create_multiple(
        token=TOKEN,
        names=names,
        region="lon1",
        image='ubuntu-16-04-x64',
        size_slug='512mb',
        ssh_keys=manager.get_all_sshkeys(),
        private_networking=True)
    tag.add_droplets(droplets)
    droplets[0].get_actions()[0].wait()
    ips = []
    for node in droplets:
        node.load()
        ips.append(node.ip_address)
    time.sleep(10)
    return ips


def setup_new_node():
    hosts = create_nodes("myApp", 1)
    execute(setup_node, hosts=hosts)


def setup_node():
    fabtools.deb.update_index()
    fabtools.deb.install([
        "nginx",
        "mysql-server",
        "php-fpm",
        "php-mysql"
    ], update=True)
    sudo("mysql_secure_installation")
    put("nginx.conf", "/etc/nginx/sites-available/default")
    systemd.restart("nginx")
    with cd(APP_DIR):
        fabtools.git.clone(APP_REPO)


def deploy():
    with cd(APP_DIR):
        fabtools.git.pull(".")
        # INSTALL DEPENDENCIES USING COMPOSER, PIP, BUNDLE ...
        # DO DATABASE MIGRATIONS
    systemd.reload("nginx")


def delete_all_nodes():
    for node in manager.get_all_droplets():
        node.destroy()
