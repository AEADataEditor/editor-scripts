const puppeteer = require("puppeteer");
const path = require("path");

const VERSION = "2025-09-06";

async function downloadPdfFromHtmlFile(htmlFilePath, outputPath) {
  const browser = await puppeteer.launch({ 
    headless: "new",
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process', // This flag is sometimes needed in Docker
      '--disable-gpu',
      '--font-render-hinting=none' // Better font rendering
    ]
  });
  const page = await browser.newPage();

  // Load HTML content from the file
  const absolutePath = path.resolve(htmlFilePath);
  await page.goto(`file://${absolutePath}`, { waitUntil: "networkidle0" });

  // Generate PDF from the page content
  await page.pdf({ 
    path: outputPath, 
    format: "Letter",
    printBackground: true, // Include background colors and images
    preferCSSPageSize: true
  });

  // Close the browser
  await browser.close();
}

const inputHtmlFile = "REPLICATION.html";
const tempFile = "/tmp/test.pdf"; // Write to tmp first
const outputFile = "REPLICATION.pdf"; 

console.log(`PDF Converter v${VERSION}`);

downloadPdfFromHtmlFile(inputHtmlFile, tempFile)
  .then(() => {
    console.log(`PDF generated successfully at: ${tempFile}`);
    // Copy from tmp to project directory with proper permissions
    const fs = require('fs');
    fs.copyFileSync(tempFile, outputFile);
    console.log(`PDF ${outputFile} copied to project directory`);
  })
  .catch((error) => console.error("Error:", error));