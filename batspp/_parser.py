#!/usr/bin/env python3
#
# Parser module
#
# This module is responsible for building
# an abstract syntax tree (AST) for Batspp
#
## TODO: solve: Setup and Continue referenced before
##       assignment should print the correct line, not the next.


"""
Parser module

This module is responsible for building
an Abstract Syntax Tree (AST) for Batspp
"""


# Standard packages
## NOTE: this is empty for now

# Installed packages
from mezcla import debug

# Local packages
from batspp._exceptions import (
    error, warning_not_intended_for_cmd,
    )
from batspp._token import (
    TokenVariant, Token,
    )
from batspp._ast_nodes import (
    AST, TestsSuite, Test,
    Assertion, AssertionType,
    )


class Parser:
    """
    This is responsible for building an
    abstract syntax tree (AST) for Batspp
    """

    def __init__(self) -> None:
        # Global states variables
        self.tokens = []
        self.index = 0
        self.last_reference = ''
        self.tests_ast_nodes_stack = []
        self.setup_commands_stack = []
        self.teardown_commands_stack = []
        self.embedded_tests = False

    def reset_global_state_variables(self) -> None:
        """Reset global states variables"""
        self.__init__()

    def get_current_token(self) -> Token:
        """Returns current token"""

        result = self.peek_token(0)

        debug.trace(7, f'parser.get_current_token() => {result}')
        return result

    def peek_token(self, number:int =1) -> Token:
        """Peek next NUMBER of tokens ahead"""

        moved_index = self.index + number

        result = None

        # We dont get the last token because should be EOF
        if moved_index < len(self.tokens):
            result = self.tokens[moved_index]

        debug.trace(7, f'parser.peek_token(number={number}) => {result}')
        return result

    def eat(self, token_variant:TokenVariant) -> None:
        """
        Compare current token variant with TOKEN_VARIANT and
        if matchs, advance token otherwise raise exception
        """
        debug.trace(7, f'parser.eat(token_variant={token_variant})')

        assert token_variant, 'invalid token_variant'

        current_token = self.get_current_token()

        if current_token.variant is token_variant:
            self.index += 1
        else:
            error(
                message=f'Expected {token_variant} but founded {current_token.variant}',
                text_line=current_token.data.text_line,
                line=current_token.data.line,
                )

    def eat_some(self, *token_variants:TokenVariant) -> None:
        """Eat some token variant in TOKEN_VARIANTS"""
        eated = False
        for variant in token_variants:
            if self.get_current_token().variant is variant:
                self.eat(variant)
                eated = True
                break
        if not eated:
            error(
                message=f'Expected {token_variants} but founded {self.get_current_token().variant}',
                text_line=self.get_current_token().data.text_line,
                line=self.get_current_token().data.line,
                )

    def is_command_next(self) -> bool:
        """
        Check if a command token pattern is next
        command : PESO TEXT
        """

        result = False
        first = self.get_current_token()
        second = self.peek_token(1)

        if second is not None:
            result = (
                first.variant is TokenVariant.PESO
                and second.variant is TokenVariant.TEXT
                )

        debug.trace(7, (
            f'parser.is_command_next() =>'
            f' next tokens variants: {first} {second}'
            f' => {result}'
            ))
        return result

    def is_setup_command_next(self) -> bool:
        """
        Check for setup command token pattern next
        setup : command ^[TEXT]
        """
        result = self.is_command_next() and not self.is_command_assertion_next()
        debug.trace(7, (
            f'parser.is_setup_command_next() => {result}'
            ))
        return result

    def is_command_assertion_next(self) -> bool:
        """
        Check if a command assertion tokens pattern is next
        command_assertion : command TEXT
        """
        result = False
        if (self.get_current_token().variant is TokenVariant.PESO
            and self.peek_token(1).variant is TokenVariant.TEXT):

            peek_advance = 2
            while self.peek_token(peek_advance) and self.peek_token(peek_advance+1):
                if self.peek_token(peek_advance).variant is TokenVariant.GREATER:
                    peek_advance += 1
                else:
                    break
                if self.peek_token(peek_advance).variant is TokenVariant.TEXT:
                    peek_advance += 1
                else:
                    break

            result = self.peek_token(peek_advance).variant is TokenVariant.TEXT

        debug.trace(7, (f'parser.is_command_assertion_next() => {result}'))
        return result

    def is_arrow_assertion_next(self, offset=0) -> bool:
        """
        Check if a arrow assertion tokens pattern is next, an OFFSET
        could be setted to peek more tokens advanced than now.
        arrow_assertion : TEXT (ASSERT_EQ|ASSERT_NE) TEXT
        """
        result = False
        first_token = self.peek_token(0 + offset)
        second_token = self.peek_token(1 + offset)
        third_token = self.peek_token(2 + offset)
        if first_token and second_token and third_token:
            result = (
                first_token.variant is TokenVariant.TEXT
                and second_token.variant in [TokenVariant.ASSERT_EQ, TokenVariant.ASSERT_NE]
                and third_token.variant is TokenVariant.TEXT
                )
        debug.trace(7, (
            f'parser.is_arrow_assertion_next() => {result}'
            ))
        return result

    def is_assertion_next(self) -> bool:
        """
        Check if a assertion tokens pattern is next
        """
        result = self.is_command_assertion_next() or self.is_arrow_assertion_next()
        debug.trace(7, (
            f'parser.is_assertion_next() => {result}'
            ))
        return result

    def is_text_paragraph_next(self) -> bool:
        """Check if text tokens pattern are next, and if not are part of a assertion"""
        is_valid_text = self.get_current_token().variant is TokenVariant.TEXT
        is_valid_new_line = (
            self.get_current_token().variant is TokenVariant.NEW_LINE
            and not self.embedded_tests
            )
        is_last_new_line = (
            self.get_current_token().variant is TokenVariant.NEW_LINE
            and self.peek_token(1).variant not in [TokenVariant.TEXT, TokenVariant.NEW_LINE]
            )
        result = (
            (is_valid_new_line or is_valid_text)
            and not self.is_arrow_assertion_next(offset=1)
            and not is_last_new_line
            )
        ## TODO: add trace
        return result

    def push_test_ast_node(self, reference:str='') -> None:
        """
        Push test AST node to tests stack,
        Set REFERENCE as reference, otherwise (if empty), search for TEST TEXT tokens
        """
        debug.trace(7, f'parser.push_test_ast_node(reference={reference})')

        data = self.get_current_token().data

        if not reference:
            self.eat(TokenVariant.TEST)
            reference = self.get_current_token().value.strip()
            self.last_reference = reference
            self.eat(TokenVariant.TEXT)

        self.tests_ast_nodes_stack.append(
            Test(reference=reference, assertions=None, data=data)
            )

        self.break_setup_assertion(reference)

    def pop_tests_ast_nodes(self) -> list:
        """
        Pop all tests ast nodes in stack
        """
        debug.trace(7, 'parser.pop_tests_ast_nodes()')
        result = self.tests_ast_nodes_stack
        self.tests_ast_nodes_stack = []
        return result

    def break_continuation(self) -> None:
        """
        Process and break continuation block tokens
        """
        debug.trace(7, 'parser.break_continuation()')

        # Continuation blocks e.g.
        #
        #   # Continuation
        #   $ command-setup
        #   $ another-command-setup
        #   $ command
        #   expected-output
        #
        # Are break into setup commands or assertion nodes
        #
        # If continuation has no reference token,
        # set reference to the last test

        data = self.get_current_token().data

        self.eat(TokenVariant.CONTINUATION)

        reference = ''

        # Check for reference
        if self.get_current_token().variant is TokenVariant.POINTER:
            self.eat(TokenVariant.POINTER)
            reference = self.get_current_token().value.strip()
            self.eat(TokenVariant.TEXT)

        # Assign continuation to last test
        elif self.last_reference:
            reference = self.last_reference

        # Otherwise the continuation is invalid
        else:
            error(
                message='Continuation without test assigned',
                text_line=data.text_line,
                line=data.line,
                column=data.column,
                )

        self.break_setup_assertion(reference)

    def break_setup_assertion(self, reference:int = '') -> None:
        """
        Process and break block test
        into setup commands and assertion AST nodes and set REFERENCE as reference
        """
        debug.trace(7, f'parser.break_setup_assertion(reference={reference})')
        assert reference, 'Invalid empty reference'

        # This unifies setup-assertions separated by a new line
        last_was_setup = False

        while True:
            if self.get_current_token().variant is TokenVariant.NEW_LINE and last_was_setup:
                self.eat(TokenVariant.NEW_LINE)
            elif self.is_setup_command_next():
                # Only setups commands can be present on a
                # block assertion, not teardowns
                self.push_setup_commands(reference)
                last_was_setup = True
            elif self.is_assertion_next():
                self.build_assertion(reference)
                last_was_setup = False
            else:
                break

    def push_setup_commands(self, reference:str='') -> None:
        """
        Push Setup commands to stack and set REFERENCE as reference
        """
        debug.trace(7, f'parser.push_setup_commands(reference={reference})')

        data = self.get_current_token().data

        # Check reference
        if not reference:
            self.eat(TokenVariant.SETUP)

            # Local setups contains reference
            if self.get_current_token().variant is TokenVariant.POINTER:
                self.eat(TokenVariant.POINTER)
                reference = self.get_current_token().value.strip()
                self.eat(TokenVariant.TEXT)

            # If there are a previus test to the setup,
            # we assign the setup to that test
            elif self.last_reference:
                reference = self.last_reference

            # Otherwise we treat the setup as a
            # global setup (empty reference)
            else:
                pass

        # Extract setup commands
        commands = self.extract_next_commands()
        if not commands:
            error(
                message = 'Setup comamnds cannot be empty',
                text_line = data.text_line,
                line = data.line,
                column = data.column,
                )

        self.setup_commands_stack.append((reference, commands))

    def pop_setup_commands(self, reference: str) -> list:
        """
        Pop setup commands from stack with same REFERENCE,
        if several setups commands blocks are founded, unify all into one
        """
        result = []
        new_setup_stack = []

        # Get commands from stack with same reference
        for stack_reference, commands in self.setup_commands_stack:
            if stack_reference == reference:
                result += commands
            else:
                new_setup_stack.append((stack_reference, commands))

        self.setup_commands_stack = new_setup_stack
        return result

    def push_teardown_commands(self) -> None:
        """
        Push teardown commands to stack
        """
        debug.trace(7, 'parser.push_teardown_commands()')
        data = self.get_current_token().data
        self.eat(TokenVariant.TEARDOWN)
        commands = self.extract_next_commands()
        if not commands:
            error(
                message = 'Teardown comamnds cannot be empty',
                text_line = data.text_line,
                line = data.line,
                column = data.column,
                )
        self.teardown_commands_stack.append(commands)

    def pop_teardown_commands(self) -> None:
        """
        Pop teardown commands from stack
        """
        debug.trace(7, 'parser.pop_teardown_commands()')
        result = self.teardown_commands_stack
        self.teardown_commands_stack = []
        return result

    def extract_next_command(self) -> str:
        """
        Return commands from next token pattern, return in a list
        command : PESO TEXT (GREATER TEXT)*
        """
        commands = []

        self.eat(TokenVariant.PESO)
        commands.append(self.get_current_token().value)
        self.eat(TokenVariant.TEXT)

        while self.get_current_token().variant is TokenVariant.GREATER:
            self.eat(TokenVariant.GREATER)
            commands.append(self.get_current_token().value)
            self.eat(TokenVariant.TEXT)

        return commands

    def extract_next_commands(self) -> list:
        """Extract N commands next"""
        result = []
        while self.is_setup_command_next():
            result += self.extract_next_command()
        return result

    def extract_text_lines(self) -> list:
        """Extract N text lines next, not extract last new line"""
        result = []
        while self.is_text_paragraph_next():
            result.append(self.get_current_token().value)
            self.eat_some(TokenVariant.TEXT, TokenVariant.NEW_LINE)
        return result

    def build_assertion(self, reference:str='') -> None:
        """
        Build and append Assertion AST node and set REFERENCE as reference
        """
        debug.trace(7, f'parser.build_assertion(reference={reference})')
        assert reference, 'Invalid empty reference'

        data = self.get_current_token().data
        atype = None
        actual = []

        # BAD:
        #   Do not use is_command_assertion_next or is_arrow_assertion_next here.
        #   because we need to check only the first token to ensure what assertion is next.

        # Check for command assertion
        ## TODO: move this to a different method (e.g. eat_command_assertion???)
        if self.get_current_token().variant is TokenVariant.PESO:
            atype = AssertionType.OUTPUT
            actual = self.extract_next_command()

        # Check for arrow assertion
        ## TODO: move this to a different method (e.g. eat_arrow_assertion???)
        elif self.get_current_token().variant is TokenVariant.TEXT:
            actual = [self.get_current_token().value]
            self.eat(TokenVariant.TEXT)

            # Check for assertion type
            if self.get_current_token().variant is TokenVariant.ASSERT_EQ:
                atype = AssertionType.EQUAL
                self.eat(TokenVariant.ASSERT_EQ)
            elif self.get_current_token().variant is TokenVariant.ASSERT_NE:
                atype = AssertionType.NOT_EQUAL
                self.eat(TokenVariant.ASSERT_NE)

        # Check expected text tokens
        expected = self.extract_text_lines()

        # New assertion node
        node = Assertion(
            atype=atype,
            setup_commands=self.pop_setup_commands(reference=reference),
            actual=actual,
            expected=expected,
            data=data,
            )

        self.assign_child_assertion_to_parent_test(node, reference)

    def assign_child_assertion_to_parent_test(
            self,
            assertion_node: Assertion,
            reference: str
            ) -> None:
        """
        Assign child assertion ast node into parent test ast node
        """
        for test in reversed(self.tests_ast_nodes_stack):
            if test.reference == reference:
                test.assertions.append(assertion_node)
                assertion_node = None
                break
        if assertion_node is not None:
            error(
                message=f'Assertion "{reference}" referenced before assignment.',
                text_line=assertion_node.data.text_line,
                line=assertion_node.data.line,
                column=None,
                )

    def build_tests_suite(self) -> AST:
        """
        Build AST node for test suite
        """

        # Extract main nodes from tokens list
        # (Test, Setup, Assertion)
        while self.get_current_token() is not None:
            current_token = self.get_current_token()
            token_variant = current_token.variant

            # Skip minor tokens
            if token_variant is TokenVariant.MINOR:
                self.eat(TokenVariant.MINOR)

            # Skip new lines without previous text
            elif token_variant is TokenVariant.NEW_LINE:
                self.eat(TokenVariant.NEW_LINE)

            # Process next tokens as a test directive pattern
            elif token_variant is TokenVariant.TEST:
                self.push_test_ast_node()

            # Process next tokens as a continuation directive pattern
            #
            # Continuation pattern are brak
            # into Setup and Assertions nodes
            elif token_variant is TokenVariant.CONTINUATION:
                self.break_continuation()

            # Process next tokens as a setup directive pattern
            elif token_variant is TokenVariant.SETUP:
                self.push_setup_commands()

            # Process next tokens as teardown directive pattern
            elif token_variant is TokenVariant.TEARDOWN:
                self.push_teardown_commands()

            # Create new test node for standlone commands and assertions
            elif self.is_command_next() or self.is_assertion_next():
                self.push_test_ast_node(f'test of line {current_token.data.line}')

            # (Only when embedded_tests!) skip standlone text tokens
            elif self.embedded_tests and token_variant is TokenVariant.TEXT:
                self.eat(TokenVariant.TEXT)

            # Finish
            else:
                break

        # The last token always should be an EOF
        self.eat(TokenVariant.EOF)

        result = TestsSuite(
            self.pop_tests_ast_nodes(),
            setup_commands = self.pop_setup_commands(reference=''),
            teardown_commands = self.pop_teardown_commands(),
            )

        self.check_if_setup_commands_stack_is_empty()

        debug.trace(7, f'parser.build_tests_suite() => {result}')
        return result

    def check_if_setup_commands_stack_is_empty(self) -> None:
        """
        Check if setup stack is empty, otherwise raises exception
        """
        if self.setup_commands_stack:
            ## TODO: print text and line when raise exception
            first_setup_reference, _ = self.setup_commands_stack[0]
            error(
                message=f'Setup "{first_setup_reference}" referenced before assignment.',
                )
        debug.trace(7, 'parser.check_setup_stack_is_empty() => passed!')

    def parse(
            self,
            tokens: list,
            embedded_tests:bool=False,
            ) -> AST:
        """
        Builds an Abstract Syntax Tree (AST) from TOKENS list
        """
        assert tokens, 'Tokens list cannot be empty'
        assert tokens[-1].variant is TokenVariant.EOF, 'Last token should be EOF'

        self.reset_global_state_variables()
        self.tokens = tokens
        self.embedded_tests = embedded_tests

        result = self.build_tests_suite()

        debug.trace(7, f'Parser.parse() => {result}')
        return result


if __name__ == '__main__':
    warning_not_intended_for_cmd()
