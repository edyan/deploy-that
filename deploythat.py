#!/usr/bin/env python3
import click
import click_log
import logging
import os
import re
import requests
import subprocess
import sys
from pkg_resources import parse_version
logger = logging.getLogger(__name__)
click_log.basic_config(logger)


class DeployThat():
    _base_path = os.path.abspath(os.path.dirname(__file__))
    _dir = os.getcwd()

    def __init__(self, config_file: str, logger: logging.Logger):
        os.chdir(self._dir)
        self._logger = logger
        self._get_config_file(config_file)
        self._read_config()
        self.extra_files = []


    def go_ahead(self, force: bool, run_tests: bool):
        self.force = force

        getattr(self, 'verify_setup_{}'.format(self.config['language']))()
        self.ask_version()

        self.commit('Bump version {}'.format(self.new_version))
        self.push()

        if run_tests is True:
            getattr(self, 'do_unit_tests_{}'.format(self.config['language']))()

        if self.config['ci'] is True:
            self.wait_and_ask()

        self.create_tag_and_push()
        self.update_package()


    def ask_version(self):
        method = '_find_version_{}'.format(self.config['language'])
        self.current_version = getattr(self, method)()
        self.new_version = '0.0'
        msg = 'Current version is ' + click.style(self.current_version, fg='yellow') + ', enter new'
        while parse_version(self.new_version) < parse_version(self.current_version):
            self.new_version = click.prompt(msg, default=self.current_version, type=str)

        self.patch_version_in_files()


    def do_unit_tests_php(self):
        self._logger.info('Running unit tests with phpunit ... (TBD)')
        pass
        # Testing .... Tests done !


    def do_unit_tests_python(self):
        self._logger.debug('Running local unit tests with pytest ...')
        if os.path.isfile('requirements-dev.txt'):
            self._logger.info('Found requirements-dev.txt, installing dependencies')
            self._run_cmd(['pip', 'install', '-r', 'requirements-dev.txt'])

        try:
            self._run_cmd(['pip', 'install', '-e', '.'])
            self._run_cmd(['py.test', self.config['tests_dir']])
        except RuntimeError:
            raise Exception('Local tests threw an error, run with "-v" for more info')
        except Exception as e:
            self._logger.error(str(e))
            exit(1)

        self._logger.info('Local tests done, no error')


    def commit(self, msg: str):
        logger.info('git commit : ' + msg)
        try:
            self._run_cmd(['git', 'commit'] + self.files_to_commit + ['-m', '"' + msg + '"'])
        except:
            logger.info('Nothing to commit ...')


    def create_tag_and_push(self):
        conf = self.config['git']

        try:
            r = requests.get(
                'https://api.github.com/repos/{0}/releases?access_token={1}'.format(conf['repo'], conf['token']))
            releases = r.json()
        except:
            raise Exception("Can't check if release exists. Make sure your github token is correct")

        release_name = 'v' + str(self.new_version)
        for release in releases:
            if release['tag_name'] == release_name:
                logger.info('Release {} already exists in GitHub'.format(release_name))
                return

        logger.info('Release {} does not exist in GitHub, creating'.format(release_name))
        click.echo('\n' + '-'*30)
        click.echo('Latest commits messages: \n' + self._get_logs().strip())
        click.echo('-'*30 + '\n')
        prompt = 'Type your tag message'
        tag_msg = click.prompt(prompt, default='New version ' + str(self.new_version), type=str)

        data = {
            'tag_name': release_name,
            'target_commitish': conf['push_branch'],
            'name': release_name,
            'body': tag_msg,
            }
        self._logger.debug('Posting: {}'.format(data))
        r = requests.post(
            'https://api.github.com/repos/{0}/releases?access_token={1}'.format(conf['repo'], conf['token']),
            json=data)
        if r.status_code != 201:
            raise Exception("Can't create the release on github : {}".format(r.text))

        self._logger.info('Release created')
        self._run_cmd(['git', 'pull', 'origin', conf['push_branch']])


    def push(self):
        if parse_version(self.new_version) == parse_version(self.current_version):
            logger.warning('Not a new version, pushing what has been commited before (bug fix?)')

        logger.info('Pushing to GIT')
        self._run_cmd(['git', 'push', 'origin', self.config['git']['push_branch']])


    def wait_and_ask(self):
        if click.confirm('Type "y" when the CI has finished its job, else "enter" to abort', abort=True):
            return


    def patch_version_in_files(self):
        click.echo()

        self.config['files'] = self.config['files'] + self.extra_files
        self.files_to_commit = []
        for key, file in enumerate(self.config['files']):
            logger.debug('Looking if {} can be patched'.format(file))
            if os.path.isfile(file) is False:
                logger.warning('{} does not exist, could not patch it'.format(file))
                continue

            patch = True
            if self.force is False:
                patch = click.confirm('Do you want to patch "{}" ?'.format(file))

            if patch is True:
                self._patch_file(file)
                self.files_to_commit.append(file)


    def update_package(self):
        if self.config['language'] == 'php':
            self._send_to_packagist()

        if self.config['language'] == 'python':
            self._send_to_pypi()


    def verify_setup_python(self):
        """Verify composer.json"""
        pass


    def verify_setup_python(self):
        res = self._run_cmd(['python', 'setup.py', 'check', '--restructuredtext'])
        if res.strip() != 'running check':
            self._logger.error('Error while checking your setup.py: ')
            self._logger.info(res)
            sys.exit(1)

        self._logger.info('setup.py seems fine !')


    def _find_version_php(self):
        print('PHP is not implemented yet')
        sys.exit(0)


    def _find_version_python(self):
        setup_location = self._dir + '/setup.py'
        if os.path.isfile(setup_location) is False:
            raise ValueError('I cannot find a setup.py in the current directory')

        try:
            sys.path.insert(1, self._dir)
            version = self._run_cmd(['python', 'setup.py', '--version']).strip()
        except Exception as e:
            raise ValueError('Your {} must contain a version property ({})'.format(setup_location, e))

        self.extra_files.append('setup.py')

        return str(version)


    def _get_logs(self):
        logs = subprocess.check_output(['git', 'log', r'--pretty=format:%s'])
        lines = logs.splitlines()
        msg = ''
        for line in lines:
            line = line.decode()
            if line == '"Bump version ' + self.current_version + '"':
                break

            msg += '- ' + line + '\n'

        return msg


    def _patch_file(self, file: str):
        with open(file, 'r') as stream:
            lines = stream.readlines()

        regex = re.compile(r'^(.*)version(.*)({})(.*)$'.format(re.escape(self.current_version)))
        with open(file, 'w') as stream:
            for line in lines:
                if regex.match(line):
                    logger.debug('"version" found in {}'.format(file))
                    logger.debug('Line content: "{}"'.format(line.strip()))
                    try:
                        line = regex.sub(r'\g<1>version\g<2>{}\g<4>'.format(self.new_version), line)
                    except Exception as e:
                        logger.error("Can't replace version: " + str(e))

                stream.write(line)

        logger.warning('{} patched'.format(file))


    def _run_cmd(self, cmd: list):
        self._logger.debug('Command: ' + ' '.join(cmd))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = ''
        for line in proc.stdout:
            line = line.decode()
            if line.strip() != '':
                self._logger.debug(line)
                output += line

        proc.communicate()

        if proc.returncode is not 0:
            raise RuntimeError("Command returned an error. Status was : {}".format(proc.returncode))

        return output


    def _send_to_packagist(self):
        """After pushing again, for PHP packages only"""
        logger.info('Sending your package to packagist')


    def _send_to_pypi(self):
        """After pushing again, for Python packages only"""
        package = self._run_cmd(['python', 'setup.py', '--name']).strip()

        current_version = None
        try:
            r = requests.get('https://pypi.python.org/pypi/{}/json'.format(package))
            current_version = r.json()['info']['version']
        except Exception as e:
            logger.warning('Error from pypi when checking for package existence : {}'.format(e))

        if current_version == self.new_version:
            logger.info('Package already present on PyPi with that version')
            return

        logger.info('Sending your package to pypi')
        self._run_cmd(['python', 'setup.py', 'sdist', 'bdist_wheel'])
        self._run_cmd(['twine', 'upload', 'dist/*-{}.tar.gz'.format(self.new_version)])


    def _get_config_file(self, config_file: str):
        if config_file is None:
            config_file = 'deploythat.yml'

        self._logger.debug('Config file is {}'.format(config_file))

        if os.path.isfile(config_file) is False:
            raise ValueError('{} does not exist'.format(config_file))

        self.config_file = config_file


    def _read_config(self):
        from impulsare_config import Reader

        specs_file = self._base_path + '/static/specs.yml'
        default_file = self._base_path + '/static/default.yml'

        self.config = Reader().parse(self.config_file, specs_file, default_file)


@click.command()
@click.version_option('0.2')
@click_log.simple_verbosity_option(logger)
@click.option('--config', '-c', help='Config file location', type=click.STRING)
@click.option('--verbose', '-v', default=False, is_flag=True, help='Verbose mode')
@click.option('--yes', '-y', default=False, is_flag=True, help='Answer Yes everywhere')
@click.option('--tests/--no-tests', '-t/ ', default=True, help='Run Unit tests')
def cli(config: str, verbose: bool, yes: bool, tests: bool):
    """Run all the steps to build your package"""
    # Override default formatter
    class DeployThatColorFormatter(click_log.ColorFormatter):
        colors = {
            'error': dict(fg='red'),
            'exception': dict(fg='red'),
            'critical': dict(fg='red'),
            'warning': dict(fg='yellow'),
            'info': dict(fg='green'),
            'debug': dict(fg='green'),
        }
    _default_handler = click_log.ClickHandler()
    _default_handler.formatter = DeployThatColorFormatter()
    logger.handlers = [_default_handler]

    # Set level according to options
    logger.setLevel(logging.INFO)
    if verbose is True:
        logger.setLevel(logging.DEBUG)

    # Deploy !
    deploythat = DeployThat(config, logger)
    deploythat.go_ahead(yes, tests)


def main():
    try:
        cli()
    except Exception as e:
        logger.error(str(e))
        logger.info('(Try "-v" for stack trace)')

        if logger.getEffectiveLevel() is logging.DEBUG:
            raise e

        sys.exit(1)


if __name__ == '__main__':
    main()
