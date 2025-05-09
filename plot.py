from collections import defaultdict
import matplotlib.pyplot as plt

# Simulating the content of the log.txt file
with open("log.txt", "r") as f:
    log_content = f.read()

# Extracting the numerical values from the log content
values = []
for line in log_content.split("\n"):
    if line.strip():
        value = int(line.split(":")[-1].strip())
        values.append(value)

# Plotting the distribution of values
plt.hist(
    values,
    bins=range(1, max(values) + 2),
    align="left",
    alpha=0.7,
    color="blue",
    edgecolor="black",
)
plt.xlabel("Signal Chunk Size")
plt.ylabel("Frequency")
plt.title("Distribution of Signal Chunk Sizes")
plt.xticks(range(1, max(values) + 1))
plt.grid(axis="y", alpha=0.75)
plt.show()
