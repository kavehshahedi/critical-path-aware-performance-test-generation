
from typing import Optional
from tmll.tmll_client import TMLLClient
from tmll.ml.modules.custom.critical_path_module import CriticalPathAnalysisModule


class CriticalPathGenerator:

    def __init__(self, tmll_client: TMLLClient, resample_freq: str = "1us", hotspots_top_n: int = 100):
        self.tmll_client = tmll_client
        self.resample_freq = resample_freq
        self.hotspots_top_n = hotspots_top_n

    def get_critical_path(self, trace_json_path: str, experiment_name: Optional[str] = None):
        if experiment_name is None:
            experiment_name = f"critical_path_{trace_json_path.split('/')[-1].split('.')[0]}"

        experiment = self.tmll_client.create_experiment(traces=[{"path": trace_json_path}], experiment_name=experiment_name)
        if not experiment:
            raise Exception("Experiment creation failed")

        flame_chart_output = experiment.find_outputs(keyword=["flame", "chart", "callstack"])
        if not flame_chart_output:
            raise Exception("No flame chart output found")

        cpa = CriticalPathAnalysisModule(client=self.tmll_client, experiment=experiment, resample_freq=self.resample_freq)

        critical_path = cpa.get_critical_path()
        function_stats = cpa.get_function_statistics()
        function_hotspots = cpa.get_hotspot_functions(top_n=self.hotspots_top_n)

        return critical_path, function_stats, function_hotspots
