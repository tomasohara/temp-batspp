#!/usr/bin/env bats
#
# This test file was generated using Batspp
# https://github.com/LimaBD/batspp
#

# Constants
VERBOSE_DEBUG="| hexdump -C"
TEMP_DIR="/tmp/batspp-32619"

# Setup function
# $1 -> test name
function run_setup () {
	test_folder=$(echo $TEMP_DIR/$1-$$)
	mkdir --parents "$test_folder"
	cd "$test_folder" || echo Warning: Unable to "cd $test_folder"
}

# Teardown function
function run_teardown () {
	: # Nothing here...
}

@test "test of line 1" {
	run_setup "test-of-line-1"

	# Assertion of line 2
	alias hello='echo "Hello user!"'
	shopt -s expand_aliases
	print_debug "$(hello)" "$(echo -e 'Hello user!\n')"
	[ "$(hello)" == "$(echo -e 'Hello user!\n')" ]

	run_teardown
}

@test "test of line 7" {
	run_setup "test-of-line-7"

	# Assertion of line 9
	alias count-words='wc -w'
	shopt -s expand_aliases
	print_debug "$(echo abc def ght | count-words)" "$(echo -e '3\n')"
	[ "$(echo abc def ght | count-words)" == "$(echo -e '3\n')" ]

	run_teardown
}

# This prints debug data when an assertion fail
# $1 -> actual value
# $2 -> expected value
function print_debug() {
	echo "=======  actual  ======="
	bash -c "echo \"$1\" $VERBOSE_DEBUG"
	echo "======= expected ======="
	bash -c "echo \"$2\" $VERBOSE_DEBUG"
	echo "========================"
}
