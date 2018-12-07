import copy
import os
import json
from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst import directives
import sphinx
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
    logging.basicConfig()
logger = logging.getLogger(__name__)


class EnvReport(nodes.General, nodes.Element):
    pass


class EnvReportDirective(Directive):
    """
    Directive for showing test results.
    """
    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        'env': directives.unchanged_required,
        'data': directives.unchanged_required,
        'raw': directives.flag}

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super(EnvReportDirective, self).__init__(*args, **kwargs)
        self.data_option = self.options.get('data', None)
        self.environments = self.options.get('env', None)

        if self.environments is not None:
            self.req_env_list_cpy = self.environments.split(',')
            self.req_env_list = []
            for element in self.req_env_list_cpy:
                if len(element) != 0:
                    self.req_env_list.append(element.lstrip().rstrip())
        else:
            self.req_env_list = None

        if self.data_option is not None:
            self.data_option_list_cpy = self.data_option.split(',')
            self.data_option_list = []
            for element in self.data_option_list_cpy:
                if len(element) != 0:
                    self.data_option_list.append(element.rstrip().lstrip())
        else:
            self.data_option_list = None

        self.header = ('Variable', 'Data')
        self.colwidths = (1, 1)

    def run(self):
        env = self.state.document.settings.env

        json_path = self.arguments[0]
        root_path = env.app.config.test_reports_rootdir
        if not os.path.isabs(json_path):
            json_path = os.path.join(root_path, json_path)

        if not os.path.exists(json_path):
            raise JsonFileNotFound("The given file does not exist: {0}".format(json_path))

        fp_json = open(json_path, 'r')

        try:
            results = json.load(fp_json)
        except ValueError:
            raise InvalidJsonFile("The given file {0} is not a valid JSON".format(json_path.split('/')[-1]))

        # check to see if environment is present in JSON or not
        if self.req_env_list is not None:
            not_present_env = []
            for req_env in self.req_env_list:
                if req_env not in results:
                    not_present_env.append(req_env)
            for not_env in not_present_env:
                self.req_env_list.remove(not_env)
                logger.warning("environment \'{0}\' is not present in JSON file".format(not_env))
            del not_present_env

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/
        main_section = []

        if self.req_env_list is None and 'raw' not in self.options:
            for enviro in results:
                main_section += self._crete_table_b(enviro=enviro, results=results)

        elif 'raw' not in self.options and self.req_env_list is not None:
            for req_env in self.req_env_list:
                main_section += self._crete_table_b(enviro=req_env, results=results)

        elif 'raw' in self.options and self.req_env_list is None:
            for enviro in results:
                # data option handling
                temp_dict = copy.deepcopy(results)
                temp_dict2 = copy.deepcopy(results)
                if self.data_option_list is not None:
                    for opt in temp_dict[enviro]:
                        if opt not in self.data_option_list:
                            del temp_dict2[enviro][opt]
                # option check
                    for opt in self.data_option_list:
                        if opt not in temp_dict2[enviro]:
                            logger.warning("option \'{0}\' is not present in JSON file".format(opt))

                del temp_dict

                section = nodes.section()
                section += nodes.title(text=enviro)
                results_string = json.dumps(temp_dict2[enviro], indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block['language'] = 'json'
                section += code_block  # nodes.literal_block(results, results)
                main_section += section  # nodes.literal_block(enviro, results[enviro])
                del temp_dict2

        elif 'raw' in self.options and self.req_env_list is not None:
            for enviro in self.req_env_list:
                # data option handling
                temp_dict = copy.deepcopy(results)
                temp_dict2 = copy.deepcopy(results)
                if self.data_option_list is not None:
                    for opt in temp_dict[enviro]:
                        if opt not in self.data_option_list:
                            del temp_dict2[enviro][opt]

                # option check
                for opt in self.data_option_list:
                    if opt not in temp_dict2[enviro]:
                        logger.warning("option \'{0}\' is not present in \'{1}\' environment file".format(opt, enviro))

                del temp_dict

                section = nodes.section()
                section += nodes.title(text=enviro)
                results_string = json.dumps(temp_dict2[enviro], indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block['language'] = 'json'
                section += code_block
                main_section += section
                del temp_dict2

        return main_section

    def _crete_table_b(self, enviro, results):
        main_section = []
        section = nodes.section()
        section += nodes.title(text=enviro)

        table = nodes.table()
        section += table

        tgroup = nodes.tgroup(cols=len(self.header))
        table += tgroup
        for colwidth in self.colwidths:
            tgroup += nodes.colspec(colwidth=colwidth)

        thead = nodes.thead()
        tgroup += thead
        thead += self._create_rows(self.header)

        tbody = nodes.tbody()
        tgroup += tbody
        all_data = results[enviro]

        data_option = copy.deepcopy(self.data_option_list)
        for data in all_data:
            if data_option is not None:
                if data in data_option:
                    data_option.remove(data)
                    tbody += self._create_rows((data, all_data[data]))
            else:
                tbody += self._create_rows((data, all_data[data]))

        main_section += section

        # data option check
        if data_option is not None:
            if len(data_option) != 0:
                for opt in data_option:
                    logger.warning("option \'{0}\' is not present in JSON file".format(opt))
            del data_option

        return main_section

    def _create_rows(self, row_cells):
        row = nodes.row()
        for cell in row_cells:
            entry = nodes.entry()
            row += entry
            if isinstance(cell, (list, dict)):
                results_string = json.dumps(cell, indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block['language'] = 'json'
                entry += code_block
            else:
                entry += nodes.paragraph(text=cell)
        return row


class InvalidJsonFile(BaseException):
    pass


class JsonFileNotFound(BaseException):
    pass


class InvalidEnvRequested(BaseException):
    pass
