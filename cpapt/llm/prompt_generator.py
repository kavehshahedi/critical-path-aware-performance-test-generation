from collections import defaultdict
import json
from typing import Dict, Any, List
from jinja2 import Environment, BaseLoader

from cpapt.llm.config.prompt_templates import PERFORMANCE_TEST_GENERATION_PROMPT


class PerformancePromptGenerator:

    def __init__(self, language: str = "cpp"):
        self.language = language.lower()
        self.template_data = {"performance_test_generation_prompt": PERFORMANCE_TEST_GENERATION_PROMPT}
        self.jinja_env = Environment(loader=BaseLoader())

    def _format_critical_path_data(self, critical_path_data: Dict[str, Any]) -> str:
        """Format the critical path JSON data for the prompt."""
        return json.dumps(critical_path_data, indent=2, ensure_ascii=False)

    def _extract_source_files_section(self, critical_path_data: Dict[str, Any]) -> str:
        """Extract and format source code from the critical path data."""
        file_sources = defaultdict(list)

        # Extract source code from critical path functions
        if 'critical_path' in critical_path_data and 'critical_path' in critical_path_data['critical_path']:
            functions = critical_path_data['critical_path']['critical_path'].get('functions', [])

            for func in functions:
                source_code_info = func.get('source_code', {})
                source_file = source_code_info.get('source_file', 'unknown.c')
                code = source_code_info.get('code', '')

                if code:
                    file_sources[source_file].append(code)

        output = []
        for source_file, codes in file_sources.items():
            output.append(f"File: {source_file}\n" + "="*50)
            for code in codes:
                output.append(f"{code}\n")

        return "\n".join(output) if output else ""

    def _extract_build_context_section(self, critical_path_data: Dict[str, Any]) -> str:
        """Extract build context information."""
        execution_context = critical_path_data.get('execution_context', {})

        context_info = []
        if 'cwd' in execution_context:
            context_info.append(f"Working Directory: {execution_context['cwd']}")
        if 'command' in execution_context:
            context_info.append(f"Execution Command: {execution_context['command']}")

        input_params = critical_path_data.get('input_params', {})
        if input_params:
            context_info.append("Input Parameters:")
            for key, value in input_params.items():
                context_info.append(f"  {key}: {value}")

        return "\n".join(context_info) if context_info else ""

    def _get_critical_functions_summary(self, critical_path_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract critical functions information for easy access."""
        functions = []

        if 'critical_path' in critical_path_data and 'critical_path' in critical_path_data['critical_path']:
            cp_functions = critical_path_data['critical_path']['critical_path'].get('functions', [])

            for func in cp_functions:
                function_info = {
                    'name': func.get('function_name', 'unknown'),
                    'duration_us': func.get('duration_us', 0),
                    'self_time_ns': func.get('self_time_ns', 0),
                    'source_code': func.get('source_code', {}).get('code', ''),
                    'line_number': func.get('source_code', {}).get('line_number', 0)
                }
                functions.append(function_info)

        return functions

    def generate_prompt(self, critical_path_file: str, additional_instructions: str = "", max_tests: int = 4) -> str:
        """
        Generate the complete prompt by filling in the template with data.
        """
        try:
            with open(critical_path_file, 'r', encoding='utf-8') as f:
                critical_path_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Critical path file not found: {critical_path_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing JSON file: {e}")

        template_vars = {
            'critical_path_data': self._format_critical_path_data(critical_path_data),
            'source_files_section': self._extract_source_files_section(critical_path_data),
            'build_context_section': self._extract_build_context_section(critical_path_data),
            'additional_instructions_text': additional_instructions,
            'language': self.language,
            'max_tests': max_tests
        }

        prompt_config = self.template_data.get('performance_test_generation_prompt', {})

        if not prompt_config:
            raise ValueError("No 'performance_test_generation_prompt' section found in template")

        system_prompt = prompt_config.get('system', '')
        user_prompt = prompt_config.get('user', '')

        if system_prompt:
            system_template = self.jinja_env.from_string(system_prompt)
            rendered_system = system_template.render(**template_vars)
        else:
            rendered_system = ""

        if user_prompt:
            user_template = self.jinja_env.from_string(user_prompt)
            rendered_user = user_template.render(**template_vars)
        else:
            rendered_user = ""

        if rendered_system and rendered_user:
            return f"SYSTEM:\n{rendered_system}\n\nUSER:\n{rendered_user}"
        elif rendered_user:
            return rendered_user
        else:
            return rendered_system

    def save_prompt(self, prompt: str, output_file: str):
        """Save the generated prompt to a file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(prompt)
        except Exception as e:
            raise IOError(f"Error saving prompt to file: {e}")
