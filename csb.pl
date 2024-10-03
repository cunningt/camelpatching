#!/usr/bin/perl

$ENV{JAVA_HOME} = "/opt/homebrew/Cellar/openjdk@21/21.0.4/libexec/openjdk.jdk/Contents/Home";

$vers = "4.8.1";
$dir = "camelpatching";
$patchdir = "camelpatches";

$currentprodbranch = "camel-4.8.0-branch";
$prodlocation = "prodlocation";

# Clean up directories
system("rm -rf $dir");
system("rm -rf $prodlocation");

# Clone
system("git clone git\@github.com:jboss-fuse/camel.git $dir");
#system("git clone git\@github.com:jboss-fuse/camel.git $prodlocation");

system("cp -r ~/prod/camel $prodlocation");

chdir $dir;
system("git remote add upstream git\@github.com:apache/camel.git");
system("git fetch upstream");

sleep(3);

system("git checkout -b camel-${vers}-branch upstream/camel-4.8.x");

sleep(3);

# Change the version
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.8.8/bin/mvn -DnewVersion=${vers}-SNAPSHOT versions:set");

# Apply pre-prod-maven-plugin patches, with check
open (FILEH, "ls ../$patchdir/pre-*.patch | sort -u |");
while ($file = <FILEH>) {
    chomp $file;

    system("git apply --check $file");
    system("git am --keep-cr --signoff < $file")

}
close(FILEH);

# Copy the entire product directory
system ("cp -r ../$prodlocation/product .");
system ("git add product");

sleep(3);

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.8.8/bin/mvn org.l2x6.cq:cq-camel-prod-maven-plugin:camel-prod-excludes -N");

sleep(3);

system("git add .mvn/excludes.txt");
system("git commit -a -m \"Run prod-maven-plugin for the first time\"");

system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.8.8/bin/mvn -DskipTests clean install");

sleep(3);

system("git commit -a -m \"Compile with results of prod-maven-plugin\"");

# Apply pre-prod-maven-plugin patches, with check
open (FILEH, "ls ../$patchdir/post-*.patch | sort -u |");
while ($file = <FILEH>) {
    chomp $file;

    system("git apply --check $file");
    system("git am --keep-cr --signoff < $file")

}
close(FILEH);

sleep(3);

# Build for final time - there should be no changes 
system("export JAVA_HOME=/opt/homebrew/Cellar/openjdk\@21/21.0.4/libexec/openjdk.jdk/Contents/Home; /usr/local/apache-maven-3.8.8/bin/mvn -DskipTests clean install");