"""
Template definitions for performance test generation prompts.
"""

PERFORMANCE_TEST_GENERATION_PROMPT = {
    "system": """You are a C/C++ performance engineering assistant that generates comprehensive performance unit tests using Google Benchmark framework.""",
    
    "user": """## Overview
You are an expert {{ language.upper() }} performance engineer. Your goal is to generate comprehensive Google Benchmark-based performance tests for functions identified in a critical execution path analysis.

Your responsibilities:
- Generate accurate performance benchmarks that reproduce observed timing characteristics
- Create both individual function benchmarks and integration tests
- Ensure statistical significance and proper measurement methodology
- Provide complete, runnable test suites with build instructions

## Critical Path Analysis Data
Here is the critical execution path analysis from the target program:
=========
{{ critical_path_data|trim }}
=========

## Requirements
- **Framework**: Use Google Benchmark library exclusively
- **Accuracy**: Benchmarks should complete within ±10% of observed timing
- **Coverage**: One benchmark per critical path function plus integration test
- **Input Preservation**: Use exact input values that triggered the critical path
- **Statistical Validity**: Let Google Benchmark handle iterations automatically

{%- if source_files_section|trim %}
## Source Files
Here are the source files containing the functions to benchmark:
======
{{ source_files_section|trim }}
======
{% endif -%}

{%- if build_context_section|trim %}
## Build Context
Additional build and dependency information:
======
{{ build_context_section|trim }}
======
{% endif -%}

{%- if additional_instructions_text|trim %}
## Additional Instructions
======
{{ additional_instructions_text|trim }}
======
{% endif %}

## Response
The output must be a YAML object equivalent to type $PerformanceTestSuite, according to the following Pydantic definitions:
=====
class SingleBenchmark(BaseModel):
    function_name: str = Field(description="Name of the function being benchmarked")
    benchmark_name: str = Field(description="Name of the benchmark function (e.g., 'BM_very_slow_computation')")
    input_parameters: Dict[str, Any] = Field(description="Input parameters used in the critical path")
    expected_duration_us: float = Field(description="Expected duration in microseconds based on critical path analysis")
    benchmark_code: str = Field(description="Complete C++ benchmark function implementation")
    setup_requirements: str = Field(description="Any special setup or fixture requirements. Empty string if none needed.")

class IntegrationBenchmark(BaseModel):
    benchmark_name: str = Field(description="Name of the integration benchmark")
    call_sequence: List[str] = Field(description="Sequence of function calls that represent the critical path")
    benchmark_code: str = Field(description="Complete integration benchmark implementation")
    expected_total_duration_us: float = Field(description="Expected total duration for the complete critical path")

class BuildInstructions(BaseModel):
    cmake_content: str = Field(description="Complete CMakeLists.txt content for building the benchmarks")
    compile_command: str = Field(description="Alternative compilation command if not using CMake")
    dependencies: List[str] = Field(description="List of required dependencies and how to install them")

class PerformanceTestSuite(BaseModel):
    language: str = Field(description="Programming language (should be 'cpp' or 'c')")
    framework: str = Field(description="Testing framework (should be 'google_benchmark')")
    header_includes: List[str] = Field(description="List of required header includes")
    individual_benchmarks: List[SingleBenchmark] = Field(min_items=1, description="Benchmarks for individual functions from critical path")
    integration_benchmark: IntegrationBenchmark = Field(description="Benchmark that tests the complete critical path")
    build_instructions: BuildInstructions = Field(description="Complete build setup and instructions")
    execution_notes: str = Field(description="Notes on how to run and interpret the benchmark results")
=====

Example output:

```yaml
language: {{ language }}
framework: google_benchmark
header_includes:
  - "<benchmark/benchmark.h>"
  - "<chrono>"
  - "\\"original_program.h\\""
individual_benchmarks:
- function_name: very_slow_computation
  benchmark_name: BM_very_slow_computation
  input_parameters:
    n: 35
  expected_duration_us: 2063.999
  benchmark_code: |
    static void BM_very_slow_computation(benchmark::State& state) {
        int n = 35;  // From critical path analysis
        for (auto _ : state) {
            int result = very_slow_computation(n);
            benchmark::DoNotOptimize(result);
        }
        state.SetLabel("Expected: ~2064us");
    }
    BENCHMARK(BM_very_slow_computation);
  setup_requirements: ""
integration_benchmark:
  benchmark_name: BM_critical_path_integration
  call_sequence:
    - "data_processing_pipeline(70)"
  benchmark_code: |
    static void BM_critical_path_integration(benchmark::State& state) {
        for (auto _ : state) {
            int result = data_processing_pipeline(70);
            benchmark::DoNotOptimize(result);
        }
        state.SetLabel("Critical path integration test");
    }
    BENCHMARK(BM_critical_path_integration);
  expected_total_duration_us: 3124.0
build_instructions:
  cmake_content: |
    cmake_minimum_required(VERSION 3.10)
    project(PerformanceTests)
    
    find_package(benchmark REQUIRED)
    
    add_executable(performance_tests 
        performance_tests.cpp
        original_program.cpp
    )
    target_link_libraries(performance_tests benchmark::benchmark)
  compile_command: "g++ -std=c++11 -O2 -lbenchmark -lpthread performance_tests.cpp original_program.cpp -o performance_tests"
  dependencies:
    - "Google Benchmark: sudo apt-get install libbenchmark-dev"
execution_notes: |
    Run with: ./performance_tests
    Add --benchmark_format=json for JSON output
    Use --benchmark_filter=<pattern> to run specific benchmarks
```

Use block scalar('|') to format multi-line YAML values.

Response (should be a valid YAML, and nothing else):
```yaml
"""
}