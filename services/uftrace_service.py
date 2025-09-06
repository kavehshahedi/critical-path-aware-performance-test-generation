import subprocess
import time
import json
import os


class UftraceService:

    def __init__(self, cwd=None) -> None:
        self.cwd = cwd or os.getcwd()

    def _process_trace_json(self, input_file) -> list:
        try:
            with open(input_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise Exception(f"Trace JSON file not found: {input_file}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in trace file: {e}")

        if 'traceEvents' not in data:
            raise Exception("JSON file doesn't contain 'traceEvents' array")

        for event in data['traceEvents']:
            if 'tid' not in event and 'pid' in event:
                event['tid'] = event['pid']

        data['traceEvents'] = [event for event in data['traceEvents']
                               if event.get('ph') in ['B', 'E']]

        try:
            json.dump(data['traceEvents'], open(input_file, 'w'), indent=1)
        except IOError as e:
            raise Exception(f"Failed to write processed JSON: {e}")

        funcs = []
        seen = set()
        for event in data['traceEvents']:
            if event.get('ph') == 'B':
                name = event['name']
                srcline = event.get('args', {}).get('srcline', None)
                key = (name, srcline)
                if key not in seen:
                    seen.add(key)
                    funcs.append({'name': name, 'srcline': srcline})

        return funcs

    def _run_vanilla_execution(self, command, timeout=300) -> tuple[float, subprocess.CompletedProcess]:
        try:
            start_time = time.time()
            process = subprocess.run(
                command, capture_output=True, cwd=self.cwd, timeout=timeout)
            end_time = time.time()

            if process.returncode != 0:
                stderr = process.stderr.decode('utf-8', errors='replace')
                if stderr.strip():
                    print(f"Vanilla stderr: {stderr}")

            return end_time - start_time, process

        except subprocess.TimeoutExpired:
            raise Exception(
                f"Vanilla execution timed out after {timeout} seconds")
        except Exception as e:
            raise Exception(f"Vanilla execution failed: {e}")

    def _run_instrumented_execution(self, command, output_name, timeout=400) -> tuple[float, str, subprocess.CompletedProcess[bytes], list]:
        try:
            process = subprocess.run(
                command, capture_output=True, cwd=self.cwd, timeout=timeout)

            stderr_output = process.stderr.decode('utf-8', errors='replace')
            stdout_output = process.stdout.decode('utf-8', errors='replace')

            if process.returncode != 0:
                print(f"Instrumented stderr: {stderr_output}")

            output_file = f"{output_name}.json"
            output_path = os.path.join(self.cwd, output_file)

            try:
                with open(output_path, 'w') as f:
                    dump_process = subprocess.run(['uftrace', 'dump', '--chrome', '--demangle=full', '--srcline'],
                                                  stdout=f, cwd=self.cwd, timeout=450,
                                                  stderr=subprocess.PIPE)
                if dump_process.returncode != 0:
                    stderr = dump_process.stderr.decode(
                        'utf-8', errors='replace')
                    raise Exception(f"uftrace dump failed: {stderr}")

            except subprocess.TimeoutExpired:
                raise Exception("uftrace dump timed out")
            except FileNotFoundError:
                raise Exception("uftrace command not found")
            except Exception as e:
                raise Exception(f"Failed to create trace dump: {e}")

            if not os.path.exists(output_path):
                raise Exception(
                    f"Trace output file was not created: {output_path}")

            absolute_path = os.path.abspath(output_path)
            functions = self._process_trace_json(absolute_path)

            try:
                stdout_lines = stdout_output.rstrip().splitlines()
                if len(stdout_lines) < 3:
                    raise Exception(
                        "Insufficient output lines to extract execution time")
                execution_time = float(
                    stdout_lines[-3].split(":")[1].split()[0])
            except (IndexError, ValueError) as e:
                raise Exception(f"Failed to parse execution time: {e}")

            return execution_time, absolute_path, process, functions

        except subprocess.TimeoutExpired:
            raise Exception(
                f"Instrumented execution timed out after {timeout} seconds")
        except Exception as e:
            raise Exception(f"Instrumented execution failed: {e}")

    def trace(self, vanilla_command, full_command, parameters, build,
              output_name="trace_output", only_vanilla=False) -> dict:
        try:
            if not vanilla_command or not isinstance(vanilla_command, list):
                raise Exception(
                    "Invalid vanilla_command: must be a non-empty list")

            if not only_vanilla and (not full_command or not isinstance(full_command, list)):
                raise Exception(
                    "Invalid full_command: must be a non-empty list")

            if not build or 'type' not in build or 'range' not in build:
                raise Exception(
                    "Invalid build configuration: must contain 'type' and 'range'")

            if only_vanilla:
                elapsed_time, process = self._run_vanilla_execution(
                    vanilla_command, timeout=20)

                document = {
                    'build': {'type': build['type'], 'range': build['range']},
                    'times': {'vanilla': elapsed_time},
                    'parameters': parameters,
                    'success': process.returncode == 0
                }

                print(f"Vanilla execution completed in {elapsed_time:.3f}s")

                return document

            full_time, json_path, full_process, functions = self._run_instrumented_execution(
                full_command, output_name
            )

            stdout_lines = full_process.stdout.decode(
                'utf-8', errors='replace').rstrip().splitlines()
            if stdout_lines:
                if len(stdout_lines) >= 3:
                    elapsed_line = stdout_lines[-3].strip()
                    try:
                        elapsed_value = elapsed_line.split(":")[1].split()[0]
                        print(
                            f"Elapsed time: {elapsed_value:.3f}s | Build: {build['type']} {build['range']} | Return code: {full_process.returncode}")
                    except Exception:
                        print(
                            f"{elapsed_line} | Build: {build['type']} {build['range']} | Return code: {full_process.returncode}")
                else:
                    print(
                        f"Elapsed time: N/A | Build: {build['type']} {build['range']} | Return code: {full_process.returncode}")

            document = {
                'build': {'type': build['type'], 'range': build['range']},
                'times': {'full': full_time},
                'parameters': parameters,
                'json_trace_path': json_path,
                'functions': functions,
                'success': full_process.returncode == 0
            }

            return document

        except Exception as e:
            raise Exception(f"Unexpected error during tracing: {e}")
