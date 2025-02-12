#! /usr/bin/env python
# Original Author: Balaji Senthamil Selvan
# Customer Delivery Architech
# Cisco Systems
# bsentham@cisco.com
# 11-FEB-2025
# 
# There are two parts to this script: 
# 1. Line 266: target_config.xml is the full config that will be ACR'd
# 2. Line 254: Set the device IP, usrname, and password
# 
# Enjoy - Jeremy Cohoe, jcohoe@cisco.com
#
#
from ncclient import manager
from xml.dom import minidom
from netmiko import ConnectHandler
import difflib
import lxml.etree as et
from xml.etree import ElementTree as ET
import xmltodict
from lxml import etree
from ncclient.operations import RPCError
from datetime import datetime
import time,os

get_modelled_config_running = '''<get-modelled-config-clis xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-cli-rpc">
                            <datastore>running</datastore>
                         </get-modelled-config-clis> '''
get_modelled_config_candidate = '''<get-modelled-config-clis xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-cli-rpc">
                            <datastore>candidate</datastore>
                         </get-modelled-config-clis> '''

global candidate_flag,pre_filename_shrun,file1_lines,post_filename_shrun,file2_lines

class Device:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.__ssh_session = None
        self.__netconf_session = None

    def ssh_connect(self):
        try:
            self.__ssh_session = ConnectHandler(device_type="cisco_xe",
                                                host=self.host,
                                                username=self.username,
                                                password=self.password)
            self.__ssh_session.enable()
        except Exception as e:
            print("ssh %s" %e)

    def netconf_connect(self):
        try:
            time.sleep(5)
            self.__netconf_session = manager.connect(host=self.host,
                                                     port=830,
                                                     username=self.username,
                                                     password=self.password,
                                                     hostkey_verify=False,
                                                     device_params={'name':'iosxe'},
                                                     manager_params={'timeout': 3600}
                                                     )
        except Exception as e:
            print("netconf:  %s" %e)

    def read_file(self,file_path):
        """Read the contents of a file and return a list of lines."""
        with open(file_path, 'r') as file:
            lines = file.readlines()
        return lines

    def compute_and_print_diff(self,file1_path, file2_path):
        """Compute the diff between two files and print the diff to the console."""
        file1_lines = self.read_file(file1_path)
        file2_lines = self.read_file(file2_path)
        diff_flag = False
        diff = difflib.unified_diff(file1_lines, file2_lines, fromfile=file1_path, tofile=file2_path)

        for line in diff:
            diff_flag = True
            print(line, end='')

        if not diff_flag:
                print("       No diff between Running Configuration pre and post deployment")

    def compare(File1, File2, tag):
        with open(File1, 'r') as f:
            d = set(f.readlines())

        with open(File2, 'r') as f:
            e = set(f.readlines())

        if tag == "pre":
            open('pre_check_config_diff_running_candidate.html.txt', 'w').close()  # Create the file

            with open('pre_check_config_diff_running_candidate.html.txt', 'a') as f:
                for line in list(d - e):
                    f.write(line)
        elif tag == "post":
            open('post_check_config_diff_running_candidate.html.txt', 'w').close()  # Create the file

            with open('post_check_config_diff_running_candidate.html.txt', 'a') as f:
                for line in list(d - e):
                    f.write(line)

    def get_cli_config(self,tag):
        if tag != "post_confirmed_commit":
            config_response = self.__netconf_session.dispatch(et.fromstring(get_modelled_config_running))
            config = xmltodict.parse(config_response.xml)["rpc-reply"]["result"]
            data = config["#text"]
            running_config = data
            lines2 = running_config.strip().splitlines()
            filename = str(tag)+"_running"+str(datetime.now()).replace(" ","_")+".txt"
            with open(filename, 'w') as f:
                f.write(running_config)
            print("      Running_Datastore config collected.")
            config_response = self.__netconf_session.dispatch(et.fromstring(get_modelled_config_candidate))
            config = xmltodict.parse(config_response.xml)["rpc-reply"]["result"]
            data = config["#text"]
            candidate_config = data
            lines1 = candidate_config.strip().splitlines()
            print("      Candidate_Datastore config collected.")
            filename = str(tag)+"_candidate" + str(datetime.now()).replace(" ", "_") + ".txt"
            with open(filename, 'w') as f:
                f.write(candidate_config)
            diff_flag = False
            for line in difflib.unified_diff(lines1, lines2, fromfile='candidate_config', tofile='running_config', lineterm='', n=0):
                diff_flag=True
                print (line)
            if not diff_flag:
                if tag == "pre":
                    print("       Pre-check: No diff between Running and candidate datastore")
                elif tag == "post":
                    print("       Post-check: No diff between Running and candidate datastore")
            with open("base_config.xml", 'w') as f:
                f.write('<config-ios-cli-trans xmlns ="http://cisco.com/ns/yang/Cisco-IOS-XE-cli-rpc"><clis>')
                f.write(data)
                f.write('</clis><operation>full-replace</operation></config-ios-cli-trans>')

            #Capture the sh_run _from_box and compare that file as well.
        self.ssh_connect()
        if tag == "pre":
            print("      Pre: Show_Running config collected.")
            pre_sh_run_output = self.show_run()
            pre_filename_shrun = str(tag) + "_shrun_" + str(datetime.now()).replace(" ", "_") + ".txt"
            with open(pre_filename_shrun, 'w') as f:
                for value in pre_sh_run_output:
                    f.write(str(value) + '\n')
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), pre_filename_shrun)
        elif tag == "post" or tag == "confirmed_post" or tag == "post_confirmed_commit":
            print("      Post: Show_Running config collected.")
            post_sh_run_output = self.show_run()
            post_filename_shrun = str(tag) + "_shrun_" + str(datetime.now()).replace(" ", "_") + ".txt"
            with open(post_filename_shrun, 'w') as f:
                for value in post_sh_run_output:
                    f.write(str(value) + '\n')
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), post_filename_shrun)

    def discard(self):
        discard_response = self.__netconf_session.discard_changes()
        print(discard_response)

    def commit(self):
        try:
            commit_response = self.__netconf_session.commit()
            print(commit_response)
        except RPCError as e:
            print(f"RPC error info::  {e.info}")
            print(f"RPC error message:: {e.message}")
        print("Candidate configuration committed.")

    def confirmed_commit(self):
        self.ssh_connect()
        pre_check = self.show_run()
        print("Initiating Confirmed Commit with Confirmed-timeout - 120 secs. ")
        try:
            self.__netconf_session.commit(confirmed=True, timeout="120", persist="session_id")
        except RPCError as e:
            print(f"RPC error info::  {e.info}")
            print(f"RPC error message:: {e.message}")
        print("Confirmed commit start time : %s " % datetime.now())
        time.sleep(10)
        self.ssh_connect()
        post_check = self.show_run()
        with open('config_diff.html', 'w') as diff_file:
            diff = difflib.HtmlDiff()
            diff_file.write(diff.make_file(pre_check, post_check))

    def check_in_sync_progress(self,xmlresponse):
        # Parse the XML
        root = etree.fromstring(xmlresponse)
        # Define the namespace map to be used for finding elements
        namespaces = {
            'ns': 'urn:ietf:params:xml:ns:netconf:base:1.0'
        }
        # Find the error-message element using XPath
        message_elements = root.xpath('//ns:error-message', namespaces=namespaces)
        # Extract and print the message text
        if message_elements:
            message = message_elements[0].text.strip()
            if "resource denied: Sync is in progress" in message:
                return True
                print(f"Extracted message: {message}")
            else:
                print("Message element not found.")
                return False

    def edit_config(self, xml_file):
        #self.ssh_connect()
        #pre_check = self.show_run()
        #print(pre_check)
        dispatch_flag = True
        while(dispatch_flag):
            tree = et.parse(xml_file)
            root = tree.getroot()
            xmlstr = ET.tostring(root, method='xml')
            try:
                response = self.__netconf_session.dispatch(et.fromstring(xmlstr))
                data = response.xml
            except RPCError as e:
                data = e.xml
                print(f"RPC error info::  {e.info}")
                print(f"RPC error message:: {e.message}")
                pass
            except Exception as e:
                traceback.print_exc()
            # beautify output
            if et.iselement(data):
                data = et.tostring(data, pretty_print=True).decode()
            try:
                out = et.tostring(
                    et.fromstring(data.encode('utf-8')),
                    pretty_print=True
                    ).decode()
            except Exception as e:
                traceback.print_exc()
            print("RPC Response : %s" %out)
            dispatch_flag = self.check_in_sync_progress(out)
            if dispatch_flag:
                print(" Re-trying dispatch after 30 sec...)")
                time.sleep(30)

    def restore_initial(self, xml_file):
        with open(xml_file, 'r') as f:
            rpc_config = f.read()
        c = self.__netconf_session.edit_config(rpc_config, target='candidate', default_operation="replace")
        self.__netconf_session.commit()
        print(c)

    def show_run(self):
        return self.__ssh_session.send_command('show run').splitlines()

if __name__ == '__main__':

    my_device = Device('10.85.134.92', 'admin', 'your_super_secret_password_here')
    my_device.netconf_connect()

    my_device.discard()

    # Run this onces to get XML Config into base_config.xml and then comment
    print("INFO: Getting the modelled_cli config - Pre-check...")
    pre_shrun_file = my_device.get_cli_config("pre")

    #Actual Test
    print("INFO: Applying the target_config...")
    print("start time : %s " %datetime.now())
    my_device.edit_config('target_config.xml')
    print("End time : %s " %datetime.now())
    print("INFO: Getting the modelled_cli config - Post-check...")
    post_shrun_file = my_device.get_cli_config("post")
    my_device.compute_and_print_diff(pre_shrun_file, post_shrun_file)
    print(
        "Checking any config difference in the sh run configuration on the device pre and post operation...")

    my_device.confirmed_commit()

    print("INFO: Getting the modelled_cli config - post_confirmed_commit...")
    post_shrun_file = my_device.get_cli_config("post_confirmed_commit")
    print("commit start time : %s " % datetime.now())

    my_device.commit()
    my_device.compute_and_print_diff(pre_shrun_file, post_shrun_file)
    time.sleep(90)
    Confirmed_post_shrun_file = my_device.get_cli_config("confirmed_post")
    print("Checking any config difference in the sh run configuration on the device pre and confirmed_post operation...")
    my_device.compute_and_print_diff(pre_shrun_file,Confirmed_post_shrun_file)
