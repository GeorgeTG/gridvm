def reverse_find(haystack, needle, index):
    while index != 0:
        if haystack[index] == needle:
            return index
        index -= 1
    else:
        return -1


