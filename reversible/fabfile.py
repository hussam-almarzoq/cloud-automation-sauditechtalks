import os
import time

import digitalocean
import fabtools
from fabric.api import *
from fabric.contrib.files import append, exists
from fabtools import systemd
from fabtools.files import upload_template, symlink, copy, remove, move

APP_DIR = "/var/www/"
APP_REPO = "https://github.com/chapagain/crud-php-simple"
LOCAL_APP_DIR = os.path.dirname(__file__)
env.user = "root"
TOKEN = "7f52a2f91cc94d196ccb0b5279d4187adc404e31c76ea12c1c57477384473f35"
APP_SERVER_TAG = "App-Server"
DB_SERVER_TAG = "Database"
LOAD_BALANCER_TAG = "Load-Balancer"
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
    try:
        tag.add_droplets(droplets)
    except DataReadError:
        pass
    droplets[0].get_actions()[0].wait()
    ips = []
    for node in droplets:
        node.load()
        ips.append(node.ip_address)
    time.sleep(10)
    return ips


def setup_new_db_node():
    hosts = create_nodes("myDb", DB_SERVER_TAG)
    execute(setup_db, hosts=hosts)


def setup_new_lb_node():
    hosts = create_nodes("myLB", LOAD_BALANCER_TAG)
    execute(setup_lb, hosts=hosts)


def setup_new_app_node(num_instances=1):
    hosts = create_nodes("myApp", APP_SERVER_TAG, 1)
    execute(setup_app, hosts=hosts)


def setup(num_apps=1):
    setup_new_db_node()
    setup_new_app_node(num_apps)
    setup_new_lb_node()


def setup_db():
    fabtools.deb.update_index()
    fabtools.deb.install([
        "mysql-server"
    ])
    sudo("mysql_secure_installation")
    append("/etc/mysql/mysql.conf.d/mysqld.cnf", "bind-address = 0.0.0.0")
    systemd.restart("mysql")


def setup_lb():
    fabtools.deb.update_index()
    fabtools.deb.install([
        "nginx"
    ])
    ips = []
    for node in manager.get_all_droplets(APP_SERVER_TAG):
        ips.append(node.private_ip_address)
    upload_template("lb_nginx.conf", "/etc/nginx/sites-available/default", {"ips": ips}, template_dir=LOCAL_APP_DIR,
                    use_jinja=True)
    systemd.reload("nginx")


def setup_app():
    fabtools.deb.update_index()
    fabtools.deb.install([
        "nginx",
        "php-fpm",
        "php-mysql"
    ], update=True)
    put("app_nginx.conf", "/etc/nginx/sites-available/default")
    systemd.restart("nginx")
    dirname = str(int(time.time()))

    with cd(APP_DIR):
        fabtools.git.clone("https://github.com/chapagain/crud-php-simple", dirname)
        symlink(dirname, "current")


def app():
    ips = []
    for node in manager.get_all_droplets(APP_SERVER_TAG):
        ips.append(node.ip_address)
    print ips
    env.hosts = ips


def deploy():
    clone_dirname = str(int(time.time()))
    with cd(APP_DIR):
        fabtools.git.clone(APP_REPO, clone_dirname)
        if exists("previous"):
            remove("previous")
        move("current", "previous")
        symlink(clone_dirname, "current")
    systemd.reload("nginx")


def rollback():
    with cd(APP_DIR):
        remove("current")
        move("previous", "current")
    systemd.reload("nginx")


def delete_all_nodes():
    for node in manager.get_all_droplets():
        node.destroy()
