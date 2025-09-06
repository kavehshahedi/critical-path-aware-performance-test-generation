import re
import os
from typing import Optional, List, Tuple
from pathlib import Path


class FunctionExtractor:

    def __init__(self, src_dir: str):
        self.src_dir = Path(src_dir)
        if not self.src_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {src_dir}")

        self.c_extensions = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx'}

    def extract_function(self, function_name: str, file_name: Optional[str] = None,
                         line_number: Optional[int] = None, remove_comments: bool = False) -> Optional[str]:
        """Extract function definition by name, optionally from a specific file and line number"""
        if file_name:
            found_path = None
            for root, dirs, files in os.walk(self.src_dir):
                if file_name in files:
                    found_path = Path(root) / file_name
                    break
            if not found_path or not found_path.exists():
                raise FileNotFoundError(f"File not found: {file_name} in {self.src_dir} or its subdirectories")
            filepath = found_path

            return self._extract_from_file(filepath, function_name, line_number, remove_comments)
        else:
            return self._extract_from_directory(function_name, line_number, remove_comments)

    def _extract_from_directory(self, function_name: str, line_number: Optional[int] = None, remove_comments: bool = False) -> Optional[str]:
        """Search for function across all C/C++ files in the directory"""
        matches = []
        for filepath in self._get_all_source_files():
            try:
                result = self._extract_from_file(filepath, function_name, line_number, remove_comments)
                if result:
                    matches.append((filepath, result))
            except (UnicodeDecodeError, PermissionError):
                continue

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0][1]

        # Multiple matches found - if line_number provided, use it to disambiguate
        if line_number:
            for filepath, function_code in matches:
                if self._verify_line_number(filepath, function_name, line_number):
                    return function_code

        # Return first match if no line number or line number doesn't help
        return matches[0][1]

    def _extract_from_file(self, filepath: Path, function_name: str,
                           line_number: Optional[int] = None, remove_comments: bool = False) -> Optional[str]:
        """Extract function from a specific file"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()

        return self._parse_function(content, function_name, line_number, remove_comments)

    def _parse_function(self, content: str, function_name: str,
                        line_number: Optional[int] = None, remove_comments: bool = False) -> Optional[str]:
        """Parse and extract the function definition from content"""
        if remove_comments:
            content = self._remove_comments(content)
        lines = content.split('\n')

        # Find all potential function matches
        matches = []
        for i in range(len(lines)):
            if self._is_function_declaration(lines, i, function_name):
                matches.append(i)

        if not matches:
            return None

        # If line_number provided, find the closest match
        if line_number is not None:
            best_match = min(matches, key=lambda x: abs(x + 1 - line_number))
            return self._extract_complete_function(lines, best_match, function_name)

        return self._extract_complete_function(lines, matches[0], function_name)

    def _remove_comments(self, content: str) -> str:
        """Remove C/C++ comments while preserving strings"""
        result = []
        i = 0
        in_string = False
        in_char = False
        string_char = None

        while i < len(content):
            char = content[i]

            if (in_string or in_char) and char == '\\':
                result.append(char)
                if i + 1 < len(content):
                    result.append(content[i + 1])
                    i += 2
                else:
                    i += 1
                continue

            if char in ['"', "'"] and not in_char and not in_string:
                in_string = True
                string_char = char
                result.append(char)
            elif char == string_char and in_string:
                in_string = False
                string_char = None
                result.append(char)
            elif char == "'" and not in_string and not in_char:
                in_char = True
                result.append(char)
            elif char == "'" and in_char:
                in_char = False
                result.append(char)
            elif not in_string and not in_char:
                if char == '/' and i + 1 < len(content):
                    next_char = content[i + 1]
                    if next_char == '/':
                        while i < len(content) and content[i] != '\n':
                            i += 1
                        if i < len(content):
                            result.append('\n')
                        continue
                    elif next_char == '*':
                        i += 2
                        while i + 1 < len(content):
                            if content[i] == '*' and content[i + 1] == '/':
                                i += 2
                                break
                            elif content[i] == '\n':
                                result.append('\n')
                            i += 1
                        continue
                result.append(char)
            else:
                result.append(char)

            i += 1

        return ''.join(result)

    def _is_function_declaration(self, lines: List[str], start_idx: int, function_name: str) -> bool:
        """Check if the function is declared starting at lines[start_idx]"""
        current_line = lines[start_idx].strip() if start_idx < len(lines) else ""

        if not current_line or current_line.endswith(';'):
            return False

        # Check if current line contains the function signature
        pattern = rf'\b{re.escape(function_name)}\s*\('
        if re.search(pattern, current_line):
            if not self._is_inside_string_or_macro(current_line, function_name):
                return True

        if start_idx + 1 < len(lines) and not '(' in current_line:
            next_line = lines[start_idx + 1].strip()
            combined = current_line + " " + next_line

            if re.search(pattern, combined):
                if not self._is_inside_string_or_macro(combined, function_name):
                    if not current_line.endswith(';'):
                        return True

        return False

    def _is_inside_string_or_macro(self, line: str, function_name: str) -> bool:
        """Check if function name is inside a string literal or macro"""
        if '"' + function_name in line or "'" + function_name in line:
            return True

        if line.strip().startswith('#'):
            return True

        return False

    def _extract_complete_function(self, lines: List[str], start_idx: int, function_name: str) -> str:
        """Extract the complete function definition starting from start_idx"""
        function_lines = []
        i = start_idx

        brace_found = False
        while i < len(lines) and not brace_found:
            line = lines[i]
            function_lines.append(line)

            if '{' in line:
                brace_found = True

            i += 1

        if not brace_found:
            return '\n'.join(function_lines)

        brace_count = self._count_braces_in_lines(function_lines)

        while i < len(lines) and brace_count > 0:
            line = lines[i]
            function_lines.append(line)

            line_brace_count = self._count_braces_in_text(line)
            brace_count += line_brace_count

            if brace_count == 0:
                break
            i += 1

        return '\n'.join(function_lines)

    def _count_braces_in_lines(self, lines: List[str]) -> int:
        """Count braces in multiple lines"""
        return sum(self._count_braces_in_text(line) for line in lines)

    def _count_braces_in_text(self, text: str) -> int:
        """Count braces in text while ignoring those in strings and comments"""
        count = 0
        i = 0
        in_string = False
        in_char = False
        string_char = None

        while i < len(text):
            char = text[i]

            if (in_string or in_char) and char == '\\':
                i += 2
                continue

            if char in ['"', "'"] and not in_char and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif char == "'" and not in_string and not in_char:
                in_char = True
            elif char == "'" and in_char:
                in_char = False
            elif not in_string and not in_char:
                if char == '/' and i + 1 < len(text):
                    next_char = text[i + 1]
                    if next_char == '/':
                        break
                    elif next_char == '*':
                        i += 2
                        continue

                if char == '{':
                    count += 1
                elif char == '}':
                    count -= 1

            i += 1

        return count

    def _verify_line_number(self, filepath: Path, function_name: str, line_number: int) -> bool:
        """Check if the function actually starts near the specified line number"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
        lines = content.split('\n')

        search_range = range(max(0, line_number - 3), min(len(lines), line_number + 3))

        for i in search_range:
            if self._is_function_declaration(lines, i, function_name):
                return True

        return False

    def _get_all_source_files(self) -> List[Path]:
        """Get all C/C++ source files recursively"""
        files = []
        for filepath in self.src_dir.rglob('*'):
            if filepath.is_file() and filepath.suffix.lower() in self.c_extensions:
                files.append(filepath)
        return files

    def list_all_functions(self, file_name: Optional[str] = None, remove_comments: bool = False) -> List[Tuple[str, str, str]]:
        """List all functions with their signatures and file paths"""
        functions = []

        if file_name:
            # List functions from specific file
            filepath = self.src_dir / file_name
            if filepath.exists():
                file_functions = self._list_functions_in_file(filepath, remove_comments=remove_comments)
                for name, signature in file_functions:
                    functions.append((name, signature, str(filepath)))
        else:
            # List functions from all files
            for filepath in self._get_all_source_files():
                try:
                    file_functions = self._list_functions_in_file(filepath, remove_comments=remove_comments)
                    for name, signature in file_functions:
                        functions.append((name, signature, str(filepath)))
                except (UnicodeDecodeError, PermissionError):
                    continue

        return functions

    def _list_functions_in_file(self, filepath: Path, remove_comments: bool = False) -> List[Tuple[str, str]]:
        """Extract all function signatures from a single file"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()

        if remove_comments:
            content = self._remove_comments(content)

        pattern = r'''
            (?:^|\n)                    # Start of line
            \s*                         # Optional whitespace
            (?:static\s+|extern\s+|inline\s+)*  # Optional storage specifiers
            (\w+(?:\s*\*+\s*|\s+))      # Return type (group 1)
            (\w+)                       # Function name (group 2)
            \s*\(                       # Opening parenthesis
            ([^{;]*)                    # Parameters (group 3)
            \)\s*                       # Closing parenthesis
            (?=\{)                      # Followed by opening brace (lookahead)
        '''

        matches = re.finditer(pattern, content, re.MULTILINE | re.VERBOSE)
        functions = []

        for match in matches:
            return_type = match.group(1).strip()
            function_name = match.group(2).strip()
            params = match.group(3).strip()

            signature = f"{function_name}({params})" if params else f"{function_name}()"
            functions.append((function_name, signature))

        return functions

    def find_function_locations(self, function_name: str) -> List[Tuple[str, int]]:
        """Find all locations where a function is defined"""
        locations = []

        for filepath in self._get_all_source_files():
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                    lines = file.readlines()

                for i, line in enumerate(lines):
                    if self._is_function_declaration(lines, i, function_name):
                        locations.append((str(filepath), i + 1))
            except (UnicodeDecodeError, PermissionError):
                continue

        return locations
