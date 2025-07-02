#!/usr/bin/env python3
"""
Script to automatically add pytest markers to test files based on content patterns.
This helps categorize tests into fast unit tests vs integration tests.
"""

import re
from pathlib import Path
from typing import List, Set


def should_mark_as_docker(content: str) -> bool:
    """Check if test should be marked as requiring Docker."""
    docker_patterns = [
        r'docker',
        r'Docker',
        r'DockerAdapter',
        r'docker_adapter',
        r'container',
        r'build.*image',
        r'create_docker_adapter',
    ]
    
    for pattern in docker_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def should_mark_as_integration(content: str) -> bool:
    """Check if test should be marked as integration test."""
    integration_patterns = [
        r'integration',
        r'end.*to.*end',
        r'e2e',
        r'real.*file',
        r'actual.*file',
        r'temp.*file.*write',
        r'subprocess',
        r'command.*execution',
        r'external.*service',
        r'network.*request',
        r'http.*client',
        r'real.*process',
    ]
    
    for pattern in integration_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def should_mark_as_slow(content: str) -> bool:
    """Check if test should be marked as slow."""
    slow_patterns = [
        r'slow',
        r'large.*file',
        r'benchmark',
        r'performance',
        r'stress.*test',
        r'heavy.*computation',
        r'time\.sleep',
        r'wait.*for',
        r'polling',
    ]
    
    for pattern in slow_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def should_mark_as_network(content: str) -> bool:
    """Check if test should be marked as requiring network."""
    network_patterns = [
        r'requests\.',
        r'urllib',
        r'http://',
        r'https://',
        r'network',
        r'api.*call',
        r'web.*request',
        r'download',
        r'fetch.*url',
    ]
    
    for pattern in network_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def get_existing_markers(content: str) -> Set[str]:
    """Extract existing pytest markers from file content."""
    markers = set()
    marker_pattern = r'@pytest\.mark\.(\w+)'
    matches = re.findall(marker_pattern, content)
    for match in matches:
        markers.add(match)
    return markers


def add_markers_to_file(file_path: Path) -> bool:
    """Add appropriate markers to a test file. Returns True if file was modified."""
    try:
        content = file_path.read_text()
        original_content = content
        
        # Skip if file already has our markers
        existing_markers = get_existing_markers(content)
        our_markers = {'docker', 'integration', 'slow', 'network', 'unit'}
        if any(marker in existing_markers for marker in our_markers):
            return False
        
        # Determine what markers to add
        markers_to_add = []
        
        if should_mark_as_docker(content):
            markers_to_add.append('docker')
        
        if should_mark_as_integration(content):
            markers_to_add.append('integration')
        
        if should_mark_as_slow(content):
            markers_to_add.append('slow')
            
        if should_mark_as_network(content):
            markers_to_add.append('network')
        
        # If no special markers, mark as unit test
        if not markers_to_add:
            markers_to_add.append('unit')
        
        # Find the first test function and add markers before it
        test_function_pattern = r'^(def test_\w+.*?)$'
        match = re.search(test_function_pattern, content, re.MULTILINE)
        
        if match and markers_to_add:
            # Create marker decorators
            marker_lines = []
            for marker in markers_to_add:
                marker_lines.append(f'@pytest.mark.{marker}')
            
            # Insert markers before the first test function
            insert_pos = match.start()
            marker_text = '\n'.join(marker_lines) + '\n'
            content = content[:insert_pos] + marker_text + content[insert_pos:]
            
            # Write back to file
            file_path.write_text(content)
            print(f"Added markers {markers_to_add} to {file_path}")
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to process all test files."""
    test_dir = Path("tests")
    if not test_dir.exists():
        print("tests/ directory not found")
        return
    
    test_files = list(test_dir.rglob("test_*.py"))
    modified_count = 0
    
    print(f"Found {len(test_files)} test files")
    
    for test_file in test_files:
        if add_markers_to_file(test_file):
            modified_count += 1
    
    print(f"Modified {modified_count} test files")


if __name__ == "__main__":
    main()