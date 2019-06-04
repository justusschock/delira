import os
import re
from setuptools import find_packages, setup


def resolve_requirements(file):
    requirements = []
    with open(file) as f:
        req = f.read().splitlines()
        for r in req:
            if r.startswith("-r"):
                requirements += resolve_requirements(
                    os.path.join(os.path.dirname(file), r.split(" ")[1]))
            else:
                requirements.append(r)
    return requirements


def read_file(file):
    with open(file) as f:
        content = f.read()
    return content


def find_version(file):
    content = read_file(file)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", content,
                              re.M)
    if version_match:
        return version_match.group(1)


def unify_requirements(base_requirements: list, *additional_requirement_lists):
    for reqs in additional_requirement_lists:
        for req in reqs:
            if req not in base_requirements:
                base_requirements.append(req)
                
    return base_requirements


def parse_all_requirements(backend_requirement_dict: dict):
    backend_requirements = {"full": []}
    for backend_name, requirement_file in backend_requirement_dict.items():
        _reqs = resolve_requirements(
            os.path.join(os.path.dirname(__file__), requirement_file))
        backend_requirements[backend_name] = _reqs
        
        backend_requirements["full"] = unify_requirements(
            backend_requirements["full"], _reqs)
    
    return backend_requirements
                                                          

requirement_files = {"base": "requirements.txt",
                     "torch": "requirements_extra_torch.txt",
                     "torchscript": "requirements_extra.txt",
                     "tf": "requirements_extra_tf.txt"
                    }


requirement_dict = parse_all_requirements(requirement_files)

readme = read_file(os.path.join(os.path.dirname(__file__), "README.md"))
license = read_file(os.path.join(os.path.dirname(__file__), "LICENSE"))
delira_version = find_version(os.path.join(os.path.dirname(__file__), "delira",
                                           "__init__.py"))

setup(
    name='delira',
    version=delira_version,
    packages=find_packages(),
    url='https://github.com/justusschock/delira/',
    test_suite="unittest",
    long_description=readme,
    long_description_content_type='text/markdown',
    maintainer="Justus Schock",
    maintainer_email="justus.schock@rwth-aachen.de",
    license=license,
    install_requires=requirement_dict.pop("base"),
    tests_require=["coverage"],
    python_requires=">=3.5",
    extras_require=requirement_dict
)
