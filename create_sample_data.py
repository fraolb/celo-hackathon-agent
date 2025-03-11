import pandas as pd

# Create sample data for testing
sample_data = [
    {
        "project_name": "Celo NFT Marketplace",
        "project_description": "A decentralized marketplace for NFTs on Celo blockchain",
        "project_github_url": "https://github.com/celo-org/celo-monorepo",
        "project_usernames": ["user1", "user2"],
        "project_url": "https://celomarket.io"
    },
    {
        "project_name": "Celo DeFi Dashboard",
        "project_description": "A dashboard for tracking DeFi activities on Celo",
        "project_github_url": "https://github.com/ubeswap/ubeswap",
        "project_usernames": ["user3"],
        "project_url": "https://celodefi.app"
    },
    {
        "project_name": "EthGlobal Project",
        "project_description": "A project developed during ETHGlobal hackathon",
        "project_github_url": "https://github.com/ethereum/go-ethereum",
        "project_usernames": ["user4", "user5", "user6"],
        "project_url": "https://ethglobal.co"
    }
]

# Create DataFrame
df = pd.DataFrame(sample_data)

# Save to Excel
df.to_excel("sample_projects.xlsx", index=False)

print("Sample data created and saved to 'sample_projects.xlsx'")