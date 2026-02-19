# simplepreprocessor

Usage
---------

import simplecpreprocessor

There will be one function called preprocess. It can either be called with a file object or
something that looks sufficiently like a file object. See unit tests to find out what's enough
for a compatible wrapper.
Line endings are by default normalized to unix but a parameter can be given to customize this
behaviour.

Gotchas
---------

Supported macros: ifdef, ifndef, if, elif, define, undef, include, else,
pragma (only "once")

The #define directive supports both object-like and function-like macros:
 * Object-like macros: `#define NAME value`
 * Function-like macros: `#define NAME(params) body`
   - Function-like macros must have '(' immediately after the macro name
   - Supports zero or more parameters
   - Arguments are expanded before substitution
   - Nested macro calls are supported
   - A macro name without '()' is not expanded (treated as identifier)

The #if and #elif directives support constant expression evaluation including:
 * Integer constants
 * Arithmetic operators: +, -, *, /, %
 * Comparison operators: ==, !=, <, >, <=, >=
 * Logical operators: &&, ||, !
 * Bitwise operators: &, |, ^
 * The defined() operator (with or without parentheses)
 * Parentheses for grouping

If using for FFI, you may want to ignore some system headers eg for types

Limitations:
 * Multiline continuations supported but whitespace handling may not be 1:1
   with real preprocessors. Trailing whitespace is removed if before comment,
   indentation from first line is removed
 * Semi-colon handling may not be identical to real preprocessors
 * Function-like macros do not support stringification (#) or
   token pasting (##) operators