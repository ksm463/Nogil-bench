import sys
import sysconfig


def main():
    print(f"Python: {sys.version}")
    print(f"Py_GIL_DISABLED: {sysconfig.get_config_var('Py_GIL_DISABLED')}")
    print(f"GIL enabled: {sys._is_gil_enabled()}")
    print("nogil-bench is ready!")


if __name__ == "__main__":
    main()
