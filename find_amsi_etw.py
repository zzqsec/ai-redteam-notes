import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('F:\\CC\\网安\\小迪渗透\\2023网安学习\\10免杀对抗.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    low = line.lower()
    if 'amsi' in low or 'etw' in low:
        print(f'L{i}: {line.rstrip()[:200]}')
