#!/usr/bin/env python3

import os
from ruamel.yaml import YAML
import argparse
import tempfile
import hashlib
import datetime
import subprocess


class Chart():
    
    def __init__(self, chart_path):
        self._chart_path = chart_path
        self._chart_name = os.path.basename(chart_path)
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._contents = None
        self._app_version = None
        self._version = None
        self._digest = None
        self._chart_yaml_path = os.path.join(self._chart_path, 'Chart.yaml')
        with open(self._chart_yaml_path) as f:
            self._contents = self._yaml.load(f)
        self._app_version = self._contents['appVersion']
        self._version = self._contents['version']

    @property
    def name(self):
        return self._chart_name

    @property
    def version(self):
        return self._version

    @property
    def app_version(self):
        return self._app_version

    def update_version(self, new_version:str):
        self._contents['version'] = new_version
        self._write()
        self._version = new_version

    def update_app_version(self, new_version:str):
        self._contents['appVersion'] = new_version
        self._write()
        self._app_version = new_version

    def _write(self):
        with open(self._chart_yaml_path, 'w') as f:
            self._yaml.dump(self._contents, f)

    def package(self, destination_dir:str):
        package_path =os.path.join(destination_dir, self.package_name)
        subprocess.run(f"helm dependency update {self._chart_path}", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        subprocess.run(f"tar -cvzf {package_path} .", cwd=self._chart_path, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        sha256_hash = hashlib.sha256()
        with open(package_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096),b""):
                sha256_hash.update(byte_block)
        self._digest =  sha256_hash.hexdigest()

    @property
    def package_name(self) -> str:
        return f"{self._chart_name}-{self.version}.tgz"
        
    def get_index_dict(self, owner:str, repository:str, branch:str):
        return {
            'apiVersion': 'v2',
            'appVersion': self.app_version,
            'created': datetime.datetime.utcnow().isoformat() + "Z",
            'description': self._contents['description'],
            'digest': self._digest,
            'name': self.name,
            'type': 'application',
            'urls': [
                f"https://raw.githubusercontent.com/{owner}/{repository}/{branch}/{self.package_name}"
            ],
            'version': self.version
        }

class ChartsRepoHelper():
    
    def __init__(self, charts_root, owner:str, repository:str, destination_dir:str, branch:str = 'gh-pages'):
        self._owner = owner
        self._repository = repository
        self._branch = branch
        self._charts = {}
        for subdir in os.listdir(charts_root):
            chart_root = os.path.join(charts_root, subdir)
            chart_yaml_path = os.path.join(chart_root, 'Chart.yaml')
            if os.path.isfile(chart_yaml_path):
                self._charts[subdir] = Chart(chart_root)
        subprocess.run(f"git clone -q -b {branch} git@github.com:{owner}/{repository}.git --depth 1 {destination_dir}", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL) 
        self._index_path = os.path.join(destination_dir, 'index.yaml')
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._contents = {}
        with open(self._index_path) as f:
            self._contents = self._yaml.load(f)

    def _write(self):
        with open(self._index_path, 'w') as f:
            self._yaml.dump(self._contents, f)

    def update_chart(self, chart_name:str, version:str = None, appVersion:str = None):
        chart = self._charts[chart_name]
        if version:
            chart.update_version(version)
        if appVersion:
            chart.update_app_version(appVersion)

    def package_chart(self, chart_name:str, destination_dir:str, keep_last_releases:int = 10):
        chart = self._charts[chart_name]
        chart.package(destination_dir)

        if chart.name not in self._contents['entries']:
            self._contents['entries'][chart.name] = []
        
        valid_entries = [
            chart.get_index_dict(self._owner, self._repository, self._branch)
        ]
        cleanup_entries = []

        release_counter = 0
        for previous_entry in self._contents['entries'][chart.name]:
            if previous_entry['version'] == chart.version:
                continue
            release_counter+=1
            if release_counter < keep_last_releases:
                valid_entries.append(previous_entry)
            else:
                cleanup_entries.append(previous_entry)
        
        self._contents['entries'][chart.name] = valid_entries
        self._write()

        for cleanup_entry in cleanup_entries:
            chart_name = cleanup_entry['name']
            chart_version = cleanup_entry['version']
            cleanup_file = os.path.join(tmp_dir, f"{chart_name}-{chart_version}.tgz")
            if os.path.isfile(cleanup_file):
                os.remove(cleanup_file)

        subprocess.run(f"git add -A", shell=True, cwd=destination_dir, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL) 
        subprocess.run(f"git commit -m 'Add {chart.package_name}' ", shell=True, cwd=destination_dir, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        subprocess.run(f"git push origin {self._branch}", shell=True, cwd=destination_dir, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


this_file_path = os.getcwd()
chart_root = os.path.join(this_file_path, 'chart')
tmp_dir = tempfile.mkdtemp()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Description of your program')
    parser.add_argument('-c','--chart', help='Description for foo argument', required=True, type=str)
    parser.add_argument('-v','--version', help='Description for bar argument', required=False, default=None, type=str)
    parser.add_argument('-a','--appVersion', help='Description for bar argument', required=False, default=None, type=str)
    parser.add_argument('-o','--owner', help='Description for bar argument', required=True, type=str)
    parser.add_argument('-r','--repository', help='Description for bar argument', required=True, type=str)
    parser.add_argument('-b','--branch', help='Description for bar argument', required=False, default='gh-pages', type=str)
    parser.add_argument('-l','--keep-last-releases', help='Description for bar argument', required=False, default=10, type=int)
    args = vars(parser.parse_args())

    print(tmp_dir)
    charts_repo_helper = ChartsRepoHelper(chart_root, args['owner'], args['repository'], tmp_dir, args['branch'])
    charts_repo_helper.update_chart(args['chart'], args['version'], args['appVersion'])
    charts_repo_helper.package_chart(args['chart'], tmp_dir, args['keep_last_releases'])


    
