# PyInstaller entry point for lurkiti, mirroring the clippiti launcher so the
# package is imported as a package in the frozen build.
from lurkiti.main import main

if __name__ == "__main__":
  main()
