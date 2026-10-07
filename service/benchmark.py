"""Measure one real import inside the Linux collector container."""
import json
import resource
from service.pipeline import run
from service.store import Store

result=run(Store())
usage=resource.getrusage(resource.RUSAGE_SELF)
result['measurement']={'peakResidentMiB':round(usage.ru_maxrss/1024,2),'userCpuSeconds':round(usage.ru_utime,2),'systemCpuSeconds':round(usage.ru_stime,2)}
print(json.dumps(result,ensure_ascii=False))
