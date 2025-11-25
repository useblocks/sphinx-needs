Features
========

.. dropdown:: 🔍 Features

   .. needtable::
      :filter: type == "feature"
      :columns: id, title, si as "SI", parent_needs_back as "Errors"

.. feature:: Define new traceability objects in source code
   :id: FE_DEF

   Create new Sphinx-Needs directly from a single comment line in your source code.
   This feature enables developers to maintain traceability information right at the point
   of implementation, ensuring that requirements, specifications, and code remain synchronized.

   By embedding traceability markers in comments, you can:

   * Define requirements, specifications, or test cases directly in source files
   * Automatically generate documentation from code comments
   * Maintain bidirectional links between documentation and implementation
   * Track coverage of requirements by implementation

   .. fault:: Traceability objects are not detected in supported languages
      :id: FAULT_1

   .. fault:: Sphinx-codelinks halucinates traceability objects
      :id: FAULT_2

.. feature:: Discover Source Code Files
   :id: FE_DISCOVERY

   Discover source code files in a specified root directory.
   The root directory shall be configurable.

.. feature:: C Language Support
   :id: FE_C_SUPPORT

   Support for defining traceability objects in C source code.

   The C language parser leverages tree-sitter to accurately identify and extract
   comments from C source files, including both single-line (``//``) and multi-line
   (``/* */``) comment styles. This ensures that traceability markers are correctly
   associated with the appropriate code structures such as functions, structs, and
   global definitions.

   Key capabilities:

   * Detection of inline and block comments
   * Association of comments with function definitions
   * Support for standard C comment conventions
   * Accurate scope detection for nested structures

   .. fault:: Traceability objects are not detected in C language
      :id: FAULT_C_1

   .. fault:: Sphinx-codelinks halucinates traceability objects in C
      :id: FAULT_C_2

.. feature:: C++ Language Support
   :id: FE_CPP

   Support for defining traceability objects in C++ source code.

   Building upon C language support, the C++ parser handles the full complexity of modern
   C++ syntax including classes, namespaces, templates, and advanced features. The tree-sitter
   based parser ensures accurate comment extraction and scope detection across various C++
   constructs.

   Enhanced features for C++:

   * Class and namespace scope detection
   * Support for C++ style comments (``//``) and C style comments (``/* */``)
   * Template and method declaration handling
   * Accurate association with member functions and constructors
   * Support for modern C++ features (C++11/14/17/20)

   .. fault:: Traceability objects are not detected in C++ language
      :id: FAULT_CPP_1

   .. fault:: Sphinx-codelinks halucinates traceability objects in C++
      :id: FAULT_CPP_2

.. feature:: Python Language Support
   :id: FE_PY

   Support for defining traceability objects in Python source code.

   The Python language parser provides comprehensive support for Python's unique comment
   and docstring conventions. It can extract traceability markers from both standard
   comments (``#``) and docstrings (triple-quoted strings), making it ideal for Python's
   documentation-driven development practices.

   Python-specific capabilities:

   * Hash-style comment (``#``) detection
   * Docstring extraction from modules, classes, and functions
   * Proper handling of multi-line comments and docstrings
   * Scope detection for functions, classes, and methods
   * Support for nested class and function definitions
   * Integration with Python's natural documentation patterns

   .. fault:: Traceability objects are not detected in Python language
      :id: FAULT_PY_1

   .. fault:: Sphinx-codelinks halucinates traceability objects in Python
      :id: FAULT_PY_2

.. feature:: YAML Language Support
   :id: FE_YAML

   Support for defining traceability objects in YAML configuration files.

   The YAML language parser provides comprehensive support for YAML's structure
   and comment conventions. It can extract traceability markers from YAML comments
   (``#``) and properly associate them with YAML structures including key-value pairs,
   list items, and nested configurations, making it ideal for documenting configuration
   files, CI/CD pipelines, and infrastructure definitions.

   YAML-specific capabilities:

   * Hash-style comment (``#``) detection
   * Inline comment support with proper structure association
   * Block comment detection and association
   * Scope detection for block mapping pairs and sequence items
   * Support for nested YAML structures
   * Document structure handling with ``---`` separators
   * Accurate association of inline comments with their corresponding structures
   * Flow and block mapping/sequence support

   .. fault:: Traceability objects are not detected in YAML language
      :id: FAULT_YAML_1

   .. fault:: Sphinx-codelinks halucinates traceability objects in YAML
      :id: FAULT_YAML_2

.. feature:: Customized comment styles
   :id: FE_CMT

   Support for different customized comment styles in source code.
   The comment structure can be defined in the configuration file.

   This feature provides flexibility to adapt Sphinx-Codelinks to your project's
   existing coding standards and conventions. Define custom markers, prefixes, and
   delimiters that match your team's documentation practices without requiring code
   changes.

   Configuration options include:

   * Custom marker syntax (e.g., ``@req``, ``#TODO``, ``//!``)
   * Configurable comment prefixes and delimiters
   * Support for language-specific comment conventions
   * Flexible pattern matching for traceability markers
   * Per-project customization via configuration files

   .. fault:: Customized comment styles are not detected in supported languages
      :id: FAULT_CMT

.. feature:: Link code to existing need items
   :id: FE_LNK

   Link code to existing need items without creating new ones, perfect for tracing
   implementations to requirements.

   This feature enables you to establish connections between your source code and
   existing documentation or requirements defined elsewhere in your Sphinx-Needs
   documentation. Instead of creating duplicate need objects, you can simply reference
   existing ones, maintaining a clean and organized traceability structure.

   Linking capabilities:

   * Reference existing requirements, specifications, or test cases by ID
   * Create bidirectional links between code and documentation
   * Avoid duplication of traceability information
   * Support for multiple links from a single code location
   * Automatic validation of link targets
   * Integration with Sphinx-Needs link visualization

   .. fault:: Linking code to existing need items fails
      :id: FAULT_LNK_1

   .. fault:: Sphinx-codelinks links code to wrong need items
      :id: FAULT_LNK_2

.. feature:: Extract blocks of reStructuredText embedded within comments
   :id: FE_RST_EXTRACTION

   Extract blocks of reStructuredText embedded within comments, allowing you to
   include rich documentation with associated metadata right next to your code.

   This powerful feature enables you to write full reStructuredText content directly
   in your source code comments, which will be extracted and processed as part of
   your Sphinx documentation. This approach brings documentation closer to implementation,
   making it easier to keep both synchronized.

   reStructuredText extraction features:

   * Full reStructuredText syntax support within comments
   * Extraction of formatted documentation blocks
   * Support for directives, roles, and inline markup
   * Preservation of indentation and formatting
   * Integration with Sphinx-Needs directives
   * Markers for block start (``@rst``) and end (``@endrst``)
   * Single-line and multi-line RST blocks

   .. fault:: Extracting reStructuredText from comments fails
      :id: FAULT_RST_EXTRACTION_1

   .. fault:: Sphinx-codelinks extracts wrong reStructuredText blocks
      :id: FAULT_RST_EXTRACTION_2

   .. fault:: Extracted reStructuredText blocks are malformed
      :id: FAULT_RST_EXTRACTION_3

.. feature:: Analyze marked content via CLI interface
   :id: FE_CLI_ANALYZE

   It shall be possible to analyze marked content via the CLI interface.

   The command-line interface provides powerful tools for analyzing and reporting on
   traceability markers in your codebase without requiring a full Sphinx build. This
   enables quick validation, continuous integration checks, and standalone reporting.

   CLI analysis capabilities:

   * Scan source files for traceability markers
   * Generate reports on found markers and their metadata
   * Validate marker syntax and structure
   * Export analysis results in various formats (JSON, CSV)
   * Integration with CI/CD pipelines
   * Fast iteration during development
   * Batch processing of multiple files or directories

   .. fault:: CLI integration fails silently
      :id: FAULT_CLI_ANALYZE_1

   .. fault:: Sphinx-codelinks halucinates marked content
      :id: FAULT_CLI_ANALYZE_2

   .. fault:: Sphinx-codelinks misses marked content
      :id: FAULT_CLI_ANALYZE_3

.. feature:: Discover the filepaths a specified root directory via CLI interface
   :id: FE_CLI_DISCOVER

   It shall be possible to specify a root directory for the CLI interface.
   All files in and below this directory shall be discovered.

   The discovery feature provides intelligent file system traversal to identify all
   relevant source files within a project structure. This enables bulk operations
   and ensures comprehensive coverage of your codebase.

   Discovery features:

   * Recursive directory traversal from specified root
   * File type filtering based on extensions
   * Respect for ignore patterns (e.g., ``.gitignore``)
   * Detection of binary vs. text files
   * Configurable include/exclude patterns
   * Support for multiple root directories
   * Efficient handling of large codebases

   .. fault:: Specifying a root directory fails
      :id: FAULT_CLI_DISCOVER_1

   .. fault:: Sphinx-codelinks discovers files outside the specified root directory
      :id: FAULT_CLI_DISCOVER_2

      Root directory setting is not respected or ignored

.. feature:: Export marked content to other formats via CLI interface
   :id: FE_CLI_WRITE

   It shall be possible to export marked content to other formats via the CLI interface.

   The export functionality enables transformation of extracted traceability data into
   various output formats for use in external tools, reports, or downstream processing.
   This makes Sphinx-Codelinks a versatile component in your documentation toolchain.

   Export capabilities:

   * JSON format for programmatic processing
   * CSV format for spreadsheet analysis
   * Sphinx-Needs compatible formats
   * Custom format definitions via templates
   * Batch export of multiple analyses
   * Filtering and transformation options
   * Integration with external reporting tools
   * Support for incremental exports

   .. fault:: Exporting marked content fails
      :id: FAULT_CLI_WRITE_1

   .. fault:: Sphinx-codelinks exports wrong content
      :id: FAULT_CLI_WRITE_2

   .. fault:: Exported content is malformed
      :id: FAULT_CLI_WRITE_3
