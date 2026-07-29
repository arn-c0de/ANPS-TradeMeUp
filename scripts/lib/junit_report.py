"""Turn a pytest JUnit XML report into lines that run.sh can colourise.

Parsing pytest's own console output looked simpler, but it silently loses
tests: long parametrised ids wrap onto a second line, and the verdict ends up
somewhere the pattern no longer matches. The XML report has one element per
test no matter how long the id is.

stdout gets one TAB-separated record per test: STATUS, test id, short reason.
The full failure text goes to the file named by argv[2] - a traceback does not
survive being squeezed onto a single line.
"""
import sys
import xml.etree.ElementTree as ET


def test_id(case):
    """Rebuild the `path/to/test.py::test_name` id pytest would print.

    Needs the `file` attribute, which only the xunit1 report family emits -
    run.sh asks for it explicitly. Without it there is no faithful way back
    from a dotted classname to a path, so fall back to the dotted form.
    """
    name = case.get("name") or "?"
    path = case.get("file")
    if not path:
        classname = case.get("classname") or ""
        return f"{classname}::{name}" if classname else name

    # For tests inside a class, classname is "tests.test_mod.TestClass" while
    # the module itself is "tests.test_mod" - keep the class in the id.
    classname = case.get("classname") or ""
    module = path[:-3].replace("/", ".") if path.endswith(".py") else ""
    if classname and module and classname != module and classname.startswith(module + "."):
        return f"{path}::{classname[len(module) + 1:]}::{name}"
    return f"{path}::{name}"


def main():
    if len(sys.argv) < 3:
        print("usage: junit_report.py <report.xml> <details-out>", file=sys.stderr)
        return 2

    try:
        tree = ET.parse(sys.argv[1])
    except (OSError, ET.ParseError) as exc:
        print(f"could not read the pytest report: {exc}", file=sys.stderr)
        return 2

    details = []
    for case in tree.iter("testcase"):
        ident = test_id(case)

        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        skipped = case.find("skipped")

        if failure is not None:
            reason = (failure.get("message") or "").strip().splitlines()
            print(f"FAIL\t{ident}\t{reason[0] if reason else ''}")
            body = (failure.text or "").rstrip()
            details.append(f"{ident}\n{'-' * len(ident)}\n{body}\n")
        elif skipped is not None:
            reason = (skipped.get("message") or "skipped").strip().splitlines()
            print(f"SKIP\t{ident}\t{reason[0] if reason else ''}")
        else:
            print(f"PASS\t{ident}\t")

    with open(sys.argv[2], "w") as handle:
        handle.write("\n".join(details))

    return 0


if __name__ == "__main__":
    sys.exit(main())
