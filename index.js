import { Client, GatewayIntentBits, EmbedBuilder, ChannelType } from 'discord.js';
import { fetchTweets } from './scraper.js';
import fs from 'fs-extra';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FOLLOWED_FILE = path.join(__dirname, 'followed.json');
const DISCORD_TOKEN = process.env.DISCORD_BOT_TOKEN;
const TARGET_CHANNEL_ID = process.env.DISCORD_CHANNEL_ID;

// Initialize Discord client
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages,
    GatewayIntentBits.GuildMembers
  ]
});

// Load followed accounts
async function loadFollowed() {
  try {
    if (await fs.pathExists(FOLLOWED_FILE)) {
      return await fs.readJSON(FOLLOWED_FILE);
    }
  } catch (error) {
    console.error('Error loading followed.json:', error);
  }
  return {};
}

// Save followed accounts
async function saveFollowed(data) {
  try {
    await fs.writeJSON(FOLLOWED_FILE, data, { spaces: 2 });
  } catch (error) {
    console.error('Error saving followed.json:', error);
  }
}

let followed = {};

// Load on startup
await (async () => {
  followed = await loadFollowed();
  console.log(`📌 Loaded ${Object.keys(followed).length} followed accounts`);
})();

client.once('ready', () => {
  console.log(`✅ Bot logged in as ${client.user.tag}`);
  console.log(`📢 Target channel: ${TARGET_CHANNEL_ID}`);
  
  // Start checking tweets every 3 minutes
  startTweetChecker();
});

client.on('messageCreate', async (message) => {
  if (!message.content.startsWith('!')) return;
  if (message.author.bot) return;

  const args = message.content.slice(1).split(/\s+/);
  const command = args[0].toLowerCase();

  try {
    if (command === 'follow' && args[1]) {
      const username = args[1].toLowerCase().replace('@', '');
      
      if (followed[username]) {
        return message.reply(`Already following @${username}`);
      }
      
      followed[username] = { lastTweetId: null };
      await saveFollowed(followed);
      message.reply(`✅ Now following @${username}`);
      console.log(`✅ Added @${username} to follow list`);
      
    } else if (command === 'unfollow' && args[1]) {
      const username = args[1].toLowerCase().replace('@', '');
      
      if (!followed[username]) {
        return message.reply(`Not following @${username}`);
      }
      
      delete followed[username];
      await saveFollowed(followed);
      message.reply(`❌ Unfollowed @${username}`);
      console.log(`❌ Removed @${username} from follow list`);
      
    } else if (command === 'list') {
      const usernames = Object.keys(followed);
      
      if (usernames.length === 0) {
        return message.reply('No accounts being followed');
      }
      
      const list = usernames.map(u => `• @${u}`).join('\n');
      message.reply(`📋 Followed accounts:\n${list}`);
      
    } else {
      message.reply('Commands: `!follow <username>` | `!unfollow <username>` | `!list`');
    }
  } catch (error) {
    console.error('Command error:', error);
    message.reply('❌ Error processing command');
  }
});

// Tweet checker loop
function startTweetChecker() {
  console.log('🔄 Starting tweet checker (every 3 minutes)');
  
  setInterval(async () => {
    await checkAllAccounts();
  }, 3 * 60 * 1000); // 3 minutes
  
  // Also check immediately on startup
  setTimeout(() => checkAllAccounts(), 5000);
}

async function checkAllAccounts() {
  if (Object.keys(followed).length === 0) {
    console.log('ℹ️ No accounts to check');
    return;
  }

  const channel = client.channels.cache.get(TARGET_CHANNEL_ID);
  if (!channel) {
    console.error(`❌ Channel ${TARGET_CHANNEL_ID} not found`);
    return;
  }

  for (const [username, data] of Object.entries(followed)) {
    try {
      console.log(`🔍 Checking @${username}...`);
      const tweets = await fetchTweets(username);
      
      if (!tweets || tweets.length === 0) {
        console.log(`  ℹ️ No tweets found`);
        continue;
      }

      // Filter new tweets (ones we haven't seen before)
      const newTweets = data.lastTweetId 
        ? tweets.filter(t => t.id !== data.lastTweetId && t.id > data.lastTweetId)
        : tweets.slice(0, 1); // Only post the latest if we haven't tracked this account yet

      if (newTweets.length === 0) {
        console.log(`  ✓ No new tweets`);
        continue;
      }

      // Post new tweets in reverse order (oldest first)
      for (const tweet of newTweets.reverse()) {
        try {
          const embed = new EmbedBuilder()
            .setAuthor({ name: `@${username}`, url: `https://x.com/${username}` })
            .setDescription(tweet.text)
            .setURL(tweet.url)
            .setColor('0x1DA1F2')
            .setFooter({ text: 'Posted from X.com' })
            .setTimestamp(new Date(tweet.timestamp));

          await channel.send({ embeds: [embed] });
          console.log(`  ✅ Posted tweet ${tweet.id}`);
        } catch (error) {
          console.error(`  ❌ Error posting tweet: ${error.message}`);
        }
      }

      // Update last seen tweet ID
      followed[username].lastTweetId = newTweets[newTweets.length - 1].id;
      await saveFollowed(followed);

    } catch (error) {
      console.error(`❌ Error checking @${username}: ${error.message}`);
    }
  }
}

// Error handling
client.on('error', error => {
  console.error('Discord client error:', error);
});

process.on('unhandledRejection', error => {
  console.error('Unhandled rejection:', error);
});

// Login
if (!DISCORD_TOKEN) {
  console.error('❌ DISCORD_BOT_TOKEN not set in .env');
  process.exit(1);
}

if (!TARGET_CHANNEL_ID) {
  console.error('❌ DISCORD_CHANNEL_ID not set in .env');
  process.exit(1);
}

client.login(DISCORD_TOKEN);
