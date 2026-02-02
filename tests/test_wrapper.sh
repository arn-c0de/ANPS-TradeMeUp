#!/bin/bash
# Simple test to verify wrapper script works

echo "Testing wrapper script..."
echo ""

# Test 1: Check if wrapper exists
if [ ! -f "scripts/run_continuous_pipeline_wrapper.sh" ]; then
    echo "FAIL: Wrapper script not found"
    read -p "Press enter to continue..."
    exit 1
fi
echo "PASS: Wrapper script exists"

# Test 2: Check if venv exists
if [ ! -f "venv/bin/python" ]; then
    echo "FAIL: venv not found"
    read -p "Press enter to continue..."
    exit 1
fi
echo "PASS: venv exists"

# Test 3: Try to start the wrapper (will open new terminal)
echo ""
echo "Opening pipeline in new terminal..."
echo "(Check the new terminal that opens)"
echo ""

# Try different terminal emulators
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "cd $(pwd) && ./scripts/run_continuous_pipeline_wrapper.sh --interval 300; exec bash"
elif command -v xterm &> /dev/null; then
    xterm -hold -e "cd $(pwd) && ./scripts/run_continuous_pipeline_wrapper.sh --interval 300" &
elif command -v konsole &> /dev/null; then
    konsole --hold -e "cd $(pwd) && ./scripts/run_continuous_pipeline_wrapper.sh --interval 300" &
else
    echo "No suitable terminal emulator found."
    echo "Please run manually: ./scripts/run_continuous_pipeline_wrapper.sh --interval 300"
fi

echo ""
echo "New terminal should have opened (if available)."
echo "Check it for any errors!"
echo ""
read -p "Press enter to continue..."
