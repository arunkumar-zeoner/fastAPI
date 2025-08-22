import pkgutil
import importlib
import pathlib

all_routers = []

package_dir = pathlib.Path(__file__).resolve().parent
for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
    module = importlib.import_module(f"{__package__}.{module_name}")
    if hasattr(module, "router"):
        all_routers.append(module.router)
